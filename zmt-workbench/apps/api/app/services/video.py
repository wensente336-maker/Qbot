"""视频服务：转写 / 粗剪（时间轴重映射）/ 分镜 / 渲染 / 质检。

均以 VideoJob 承载异步任务的请求、状态与结果。当前框架在无 Celery/Redis 的
环境下由 API 同步调用执行；接入队列后可将同一函数包装为 Celery 任务（见 tasks/）。
"""

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.asr import asr
from app.core.llm import llm
from app.core.qa import (
    build_black_detect_cmd,
    build_silence_detect_cmd,
    summarize_qa,
)
from app.core.timeline import build_remap, merge_cuts
from app.models.project import ContentProject
from app.models.video import VideoJob


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
    return await _finish(db, job, {"segments": segments})


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
    # 真实渲染由 Remotion/FFmpeg 在 render 队列执行；此处输出占位引用
    return await _finish(
        db,
        job,
        {
            "output_key": f"render-output/{project_id}/final-{job.id}.mp4",
            "duration_ms": 30000,
            "status": "placeholder",
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
