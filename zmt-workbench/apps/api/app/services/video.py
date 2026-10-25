"""视频服务：转写 / 粗剪（时间轴重映射）/ 分镜 / 渲染 / 质检。

均以 VideoJob 承载异步任务的请求、状态与结果。当前框架在无 Celery/Redis 的
环境下由 API 同步调用执行；接入队列后可将同一函数包装为 Celery 任务（见 tasks/）。
"""

import os

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.asr import SUBTITLE_MAX_CHARS, asr
from app.core.llm import llm
from app.core.qa import run_qa_checks
from app.core.remotion import mux_audio, render_composition
from app.core.render import (
    FFMPEG,
    estimated_duration_ms,
    probe_duration_ms,
    render_to_file,
)
from app.core.storage import storage
from app.core.timeline import build_remap, merge_cuts
from app.core.tts import tts
from app.models.project import ContentProject
from app.models.script import Script
from app.models.system import AssetFile
from app.models.video import VideoAsset, VideoJob
from app.services.billing import record_llm_usage
from app.services.quota import ensure_quota


async def _get_owned_project(db: AsyncSession, project_id: int, user_id: int) -> ContentProject:
    project = await db.get(ContentProject, project_id)
    if project is None or project.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "项目不存在")
    return project


async def _new_job(db: AsyncSession, project_id: int, job_type: str, request: dict) -> VideoJob:
    job = VideoJob(project_id=project_id, job_type=job_type, request=request, status="running")
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


async def _finish(db: AsyncSession, job: VideoJob, result: dict) -> VideoJob:
    job.result = result
    job.status = "succeeded"
    job.progress = 100
    await db.commit()
    await db.refresh(job)
    return job


async def transcribe_video(
    db: AsyncSession, user_id: int, project_id: int, asset_ref: str
) -> VideoJob:
    await _get_owned_project(db, project_id, user_id)
    await ensure_quota(db, "transcribe")  # 超额直接 429，不再白跑一次转写
    job = await _new_job(db, project_id, "transcribe", {"asset_ref": asset_ref})
    result = await asr.transcribe(asset_ref)  # mock 时返回占位词级时间轴
    return await _finish(db, job, result)


async def rough_cut(
    db: AsyncSession, user_id: int, project_id: int, cuts: list[tuple[int, int]]
) -> VideoJob:
    await _get_owned_project(db, project_id, user_id)
    merged = merge_cuts(cuts)
    remap_table = build_remap(merged)
    job = await _new_job(db, project_id, "editing", {"cuts": merged, "remap_table": remap_table})
    return await _finish(db, job, {"merged_cuts": merged, "remap_table": remap_table})


def _mock_storyboard(project_id: int) -> list[dict]:
    return [
        {
            "index": i,
            "start_ms": i * 3000,
            "end_ms": (i + 1) * 3000,
            "visual": f"分镜 {i}：画面说明（占位）",
            "subtitle": f"字幕第 {i} 句（占位）",
            "visual_skill": "default",
        }
        for i in range(4)
    ]


def storyboard_from_words(words: list[dict], max_chars: int = SUBTITLE_MAX_CHARS) -> list[dict]:
    """把 ASR 时间轴（词级或句内短句）打包成逐句字幕分镜。

    每行字幕不超过 max_chars，起止时间取该行首末片段，保证字幕与口播对齐。
    """
    segments: list[dict] = []
    buf: list[dict] = []

    def flush() -> None:
        if not buf:
            return
        text = "".join(w["word"] for w in buf).strip()
        if text:
            segments.append(
                {
                    "index": len(segments),
                    "start_ms": buf[0]["start_ms"],
                    "end_ms": max(buf[-1]["end_ms"], buf[0]["start_ms"]),
                    "visual": "口播画面",
                    "subtitle": text,
                    "visual_skill": "default",
                }
            )
        buf.clear()

    for word in words or []:
        token = str(word.get("word") or "").strip()
        if not token:
            continue
        item = {
            "word": token,
            "start_ms": int(word.get("start_ms") or 0),
            "end_ms": int(word.get("end_ms") or 0),
        }
        if buf and len("".join(w["word"] for w in buf)) + len(token) > max_chars:
            flush()
        buf.append(item)
    flush()
    return segments


async def generate_storyboard(
    db: AsyncSession, user_id: int, project_id: int, script_id: int | None
) -> VideoJob:
    await _get_owned_project(db, project_id, user_id)
    job = await _new_job(db, project_id, "editing", {"script_id": script_id})

    # 已有转写结果时，字幕直接用真实时间戳逐句生成，避免 LLM 编造时间轴
    transcribe_job = await _latest_job(db, project_id, "transcribe")
    words = (transcribe_job.result or {}).get("words") if transcribe_job else None
    segments = storyboard_from_words(words or [])
    if segments:
        job.request = {**(job.request or {}), "source": "asr"}
        return await _finish(db, job, {"segments": segments})

    if llm.mock_enabled:
        segments = _mock_storyboard(project_id)
    else:
        await ensure_quota(db, "llm", 0)  # 分镜走 LLM 时才校验 token 配额
        segments = await llm.json_list(
            "你是分镜导演，输出 JSON 数组，每项含 {index,start_ms,end_ms,visual,subtitle,visual_skill}。",
            f"项目 #{project_id}，脚本 ID={script_id}",
        )
        await record_llm_usage(db, project_id=project_id)
    return await _finish(db, job, {"segments": segments})


def _resolve_local_path(asset_ref: str) -> str:
    """把 asset_ref 解析为本地绝对路径；远程 URL 暂不支持本地渲染。"""
    if asset_ref.startswith(("http://", "https://")):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "渲染暂不支持远程 URL，请先本地上传")
    return asset_ref if os.path.isabs(asset_ref) else storage.local_path(asset_ref)


async def _latest_job(db: AsyncSession, project_id: int, job_type: str) -> VideoJob | None:
    return await db.scalar(
        select(VideoJob)
        .where(VideoJob.project_id == project_id, VideoJob.job_type == job_type)
        .order_by(VideoJob.id.desc())
    )


async def _resolve_render_inputs(
    db: AsyncSession, project_id: int
) -> tuple[str | None, list[dict]]:
    """解析渲染输入：素材源本地路径 + 最新分镜字幕句。"""
    source_path: str | None = None
    source_job = await _latest_job(db, project_id, "transcribe")
    if source_job and (source_job.request or {}).get("asset_ref"):
        candidate = _resolve_local_path(source_job.request["asset_ref"])
        if os.path.isfile(candidate):
            source_path = candidate

    segments: list[dict] = []
    # 粗剪与分镜同为 editing 任务，按 id 倒序取最近一个真正含分镜的版本，
    # 避免「先分镜后粗剪」把字幕时间轴覆盖掉
    editing_jobs = await db.scalars(
        select(VideoJob)
        .where(VideoJob.project_id == project_id, VideoJob.job_type == "editing")
        .order_by(VideoJob.id.desc())
        .limit(10)
    )
    for editing_job in editing_jobs:
        candidate = (editing_job.result or {}).get("segments")
        if isinstance(candidate, list) and candidate:
            segments = candidate
            break
    return source_path, segments


async def _attach_voiceover(db: AsyncSession, project_id: int, video_path: str) -> bool:
    """若项目已有口播音频，则混流进成片（Remotion / FFmpeg 出片均适用）。"""
    asset = await db.scalar(
        select(VideoAsset)
        .where(VideoAsset.project_id == project_id, VideoAsset.kind == "voiceover")
        .order_by(VideoAsset.id.desc())
    )
    if asset is None:
        return False
    audio = await db.get(AssetFile, asset.asset_file_id)
    if audio is None:
        return False
    audio_path = storage.local_path(audio.key)
    if not os.path.isfile(audio_path) or not os.path.isfile(video_path):
        return False
    return await mux_audio(video_path, audio_path)


async def render_to_asset(
    db: AsyncSession,
    job: VideoJob,
    project_id: int,
    source_path: str | None,
    segments: list[dict],
) -> dict:
    """按 `request.composition` 出片：remotion 优先，失败/未启用回退 FFmpeg。

    仅在真正产出文件时登记 AssetFile + VideoAsset；无 FFmpeg 时返回 placeholder。
    """
    request = job.request or {}
    resolution = request.get("resolution", "1080x1920")
    fps = int(request.get("fps", 30))
    composition = request.get("composition", "default")

    output_key = storage.build_key("render-output", project_id, f"final-{job.id}.mp4")
    output_path = storage.local_path(output_key)

    engine = "ffmpeg"
    duration_ms: int | None = None

    if composition == "remotion":
        duration_ms = await render_composition(segments, output_path, resolution, fps)
        if duration_ms is not None:
            engine = "remotion"

    if duration_ms is None:
        if FFMPEG is None:
            return {
                "output_key": output_key,
                "duration_ms": estimated_duration_ms(segments),
                "status": "placeholder",
            }
        duration_ms = await render_to_file(source_path, output_path, resolution, fps, segments)

    # 两种引擎产出的成片都补口播：有 voiceover 资产时替换音轨并补静音对齐视频时长
    has_voiceover = await _attach_voiceover(db, project_id, output_path)
    if has_voiceover:
        duration_ms = await probe_duration_ms(output_path) or duration_ms

    asset = AssetFile(
        bucket="local",
        key=output_key,
        url=f"/media/{output_key}",
        size_bytes=os.path.getsize(output_path),
        content_type="video/mp4",
        lifecycle="render-output",
        status="uploaded",
    )
    db.add(asset)
    await db.flush()
    db.add(VideoAsset(project_id=project_id, kind="final", asset_file_id=asset.id))

    return {
        "output_key": output_key,
        "url": f"/media/{output_key}",
        "duration_ms": duration_ms,
        "status": "rendered",
        "engine": engine,
        "voiceover": has_voiceover,
        "segments": len(segments),
    }


async def render_video(
    db: AsyncSession, user_id: int, project_id: int, composition: str, resolution: str, fps: int
) -> VideoJob:
    await _get_owned_project(db, project_id, user_id)
    await ensure_quota(db, "render")  # 出片最耗 CPU，超额直接 429
    job = await _new_job(
        db,
        project_id,
        "render",
        {"composition": composition, "resolution": resolution, "fps": fps},
    )

    source_path, segments = await _resolve_render_inputs(db, project_id)
    result = await render_to_asset(db, job, project_id, source_path, segments)
    return await _finish(db, job, result)


async def run_qa(db: AsyncSession, user_id: int, job_id: int) -> VideoJob:
    job = await db.get(VideoJob, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务不存在")
    await _get_owned_project(db, job.project_id, user_id)

    if job.job_type != "render":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "仅渲染任务可执行质检")

    output_key = (job.result or {}).get("output_key")
    if not output_key:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "该任务没有成片产物，请先完成渲染")

    output_path = storage.local_path(output_key)
    if not os.path.isfile(output_path):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "成片文件不存在，请重新渲染")

    story_job = await _latest_job(db, job.project_id, "editing")
    segments = (story_job.result or {}).get("segments", []) if story_job else []
    resolution = (job.request or {}).get("resolution", "1080x1920")

    summary = await run_qa_checks(output_path, segments=segments, resolution=resolution)
    job.result = {**(job.result or {}), "qa": summary}
    job.progress = 100
    await db.commit()
    await db.refresh(job)
    return job


async def synthesize_narration(
    db: AsyncSession, user_id: int, project_id: int
) -> VideoJob:
    """读取项目最新文案，调用 TTS 合成口播音频并登记为 voiceover 资产。"""
    await _get_owned_project(db, project_id, user_id)

    script = await db.scalar(select(Script).where(Script.project_id == project_id))
    text = (script.content or "").strip() if script else ""
    if not text:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "暂无文案，请先生成脚本")

    await ensure_quota(db, "tts_char", len(text))  # 按字数预扣，超额 429
    job = await _new_job(db, project_id, "tts", {"chars": len(text)})

    key = await tts.synthesize(text)
    if key is None:
        raise HTTPException(
            status.HTTP_501_NOT_IMPLEMENTED,
            "TTS 未接入：请配置 TTS_ENDPOINT / TTS_EDGE_VOICE / TENCENT_SECRET_ID 任一",
        )

    path = storage.local_path(key)
    asset = AssetFile(
        bucket="local",
        key=key,
        url=f"/media/{key}",
        size_bytes=os.path.getsize(path),
        content_type="audio/mpeg",
        lifecycle="render-output",
        status="uploaded",
    )
    db.add(asset)
    await db.flush()
    db.add(VideoAsset(project_id=project_id, kind="voiceover", asset_file_id=asset.id))

    return await _finish(
        db,
        job,
        {"output_key": key, "url": f"/media/{key}", "status": "synthesized", "chars": len(text)},
    )
