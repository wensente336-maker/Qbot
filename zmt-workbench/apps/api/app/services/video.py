"""视频服务：转写 / 粗剪（时间轴重映射）/ 分镜 / 渲染 / 质检。

均以 VideoJob 承载异步任务的请求、状态与结果。当前框架在无 Celery/Redis 的
环境下由 API 同步调用执行；接入队列后可将同一函数包装为 Celery 任务（见 tasks/）。
"""

import os

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.asr import asr
from app.core.llm import llm
from app.core.qa import (
    build_black_detect_cmd,
    build_silence_detect_cmd,
    summarize_qa,
)
from app.core.render import (
    FFMPEG,
    estimated_duration_ms,
    render_to_file,
)
from app.core.storage import storage
from app.core.timeline import build_remap, merge_cuts
from app.models.project import ContentProject
from app.models.system import AssetFile
from app.models.video import VideoAsset, VideoJob
from app.services.billing import record_llm_usage


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


async def generate_storyboard(
    db: AsyncSession, user_id: int, project_id: int, script_id: int | None
) -> VideoJob:
    await _get_owned_project(db, project_id, user_id)
    job = await _new_job(db, project_id, "editing", {"script_id": script_id})

    if llm.mock_enabled:
        segments = _mock_storyboard(project_id)
    else:
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
    story_job = await _latest_job(db, project_id, "editing")
    if story_job and isinstance((story_job.result or {}).get("segments"), list):
        segments = story_job.result["segments"]
    return source_path, segments


async def render_video(
    db: AsyncSession, user_id: int, project_id: int, composition: str, resolution: str, fps: int
) -> VideoJob:
    await _get_owned_project(db, project_id, user_id)
    job = await _new_job(
        db,
        project_id,
        "render",
        {"composition": composition, "resolution": resolution, "fps": fps},
    )

    source_path, segments = await _resolve_render_inputs(db, project_id)
    output_key = storage.build_key("render-output", project_id, f"final-{job.id}.mp4")
    output_path = storage.local_path(output_key)

    if FFMPEG is None:
        return await _finish(
            db, job, {
                "output_key": output_key,
                "duration_ms": estimated_duration_ms(segments),
                "status": "placeholder",
            }
        )

    duration_ms = await render_to_file(source_path, output_path, resolution, fps, segments)

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

    return await _finish(
        db,
        job,
        {
            "output_key": output_key,
            "url": f"/media/{output_key}",
            "duration_ms": duration_ms,
            "status": "rendered",
            "segments": len(segments),
        },
    )


async def run_qa(db: AsyncSession, user_id: int, job_id: int) -> VideoJob:
    job = await db.get(VideoJob, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务不存在")
    await _get_owned_project(db, job.project_id, user_id)

    # FFmpeg 命令模板（真实执行在 render 队列）；此处模拟 4 项全通过
    details = {
        "silence_cmd": build_silence_detect_cmd("{{input}}"),
        "black_cmd": build_black_detect_cmd("{{input}}"),
    }
    summary = summarize_qa(details=details)
    job.result = {"qa": summary}
    job.progress = 100
    await db.commit()
    await db.refresh(job)
    return job
