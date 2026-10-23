"""Celery 任务实现：monitor / transcribe / analyze / render。

任务通过 `asyncio.run` 调用同一套异步服务逻辑，保证 API 同步路径与 Celery
异步路径复用一致代码。幂等性依赖 task_runs 表的 (task_type, target_id, run_key)
唯一约束——同一任务重复入队只会执行一次。
"""

import asyncio
import os
from datetime import UTC, datetime

from celery.utils.log import get_task_logger
from sqlalchemy import select

from app.core.asr import asr
from app.db.session import AsyncSessionLocal
from app.models.system import TaskRun
from app.models.video import VideoJob
from app.services.billing import record_llm_usage
from app.tasks.celery_app import celery

logger = get_task_logger(__name__)


async def _claim(task_type: str, target_id: str, run_key: str) -> bool:
    """幂等抢占：已成功则返回 False（跳过），否则登记 running 并返回 True。"""
    async with AsyncSessionLocal() as db:
        existing = await db.scalar(
            select(TaskRun).where(
                TaskRun.task_type == task_type,
                TaskRun.target_id == target_id,
                TaskRun.run_key == run_key,
            )
        )
        if existing is not None and existing.status == "succeeded":
            return False
        if existing is not None:
            existing.attempts += 1
            existing.status = "running"
            existing.started_at = datetime.now(UTC)
        else:
            db.add(
                TaskRun(
                    task_type=task_type,
                    target_id=target_id,
                    run_key=run_key,
                    status="running",
                    attempts=1,
                    started_at=datetime.now(UTC),
                )
            )
        await db.commit()
        return True


async def _settle(
    task_type: str, target_id: str, run_key: str, result: dict, error: str | None = None
) -> None:
    async with AsyncSessionLocal() as db:
        run = await db.scalar(
            select(TaskRun).where(
                TaskRun.task_type == task_type,
                TaskRun.target_id == target_id,
                TaskRun.run_key == run_key,
            )
        )
        if run is not None:
            run.status = "failed" if error else "succeeded"
            run.result = result
            run.error = error
            run.finished_at = datetime.now(UTC)
            await db.commit()


@celery.task(name="app.tasks.monitor")
def monitor() -> dict:
    """对标巡检：扫描启用账号并拉取作品（未授权时返回空结果）。"""
    return asyncio.run(_monitor())


async def _monitor() -> dict:
    from app.services.benchmark import sync_benchmark

    async with AsyncSessionLocal() as db:
        return await sync_benchmark(db)


@celery.task(name="app.tasks.transcribe")
def transcribe(job_id: int) -> dict:
    return asyncio.run(_transcribe(job_id))


async def _transcribe(job_id: int) -> dict:
    target, key = str(job_id), "video_job"
    if not await _claim("transcribe", target, key):
        return {"skipped": True}
    try:
        async with AsyncSessionLocal() as db:
            job = await db.get(VideoJob, job_id)
            if job is None:
                raise ValueError(f"任务不存在：{job_id}")
            job.status = "running"
            job.progress = 10
            await db.commit()
            asset_ref = (job.request or {}).get("asset_ref", "")
            result = await asr.transcribe(asset_ref)
            job.result = result
            job.status = "succeeded"
            job.progress = 100
            await db.commit()
        await _settle("transcribe", target, key, result)
        return result
    except Exception as exc:  # noqa: BLE001
        await _settle("transcribe", target, key, {}, str(exc))
        raise


@celery.task(name="app.tasks.analyze")
def analyze(job_id: int) -> dict:
    return asyncio.run(_analyze(job_id))


async def _analyze(job_id: int) -> dict:
    from app.core.llm import llm

    target, key = str(job_id), "video_job"
    if not await _claim("analyze", target, key):
        return {"skipped": True}
    try:
        async with AsyncSessionLocal() as db:
            job = await db.get(VideoJob, job_id)
            if job is None:
                raise ValueError(f"任务不存在：{job_id}")
            job.status = "running"
            job.progress = 20
            await db.commit()
            request = job.request or {}
            if llm.mock_enabled:
                result = {"segments": [], "model": "mock"}
            else:
                result = await llm.json_list(
                    "你是分镜导演，输出 JSON 数组。", f"项目任务 {job.project_id}，参数 {request}"
                )
                await record_llm_usage(db, project_id=job.project_id, job_id=job.id)
                result = {"segments": result}
            job.result = result
            job.status = "succeeded"
            job.progress = 100
            await db.commit()
        await _settle("analyze", target, key, result)
        return result
    except Exception as exc:  # noqa: BLE001
        await _settle("analyze", target, key, {}, str(exc))
        raise


@celery.task(name="app.tasks.render")
def render(job_id: int) -> dict:
    return asyncio.run(_render(job_id))


async def _render(job_id: int) -> dict:
    from app.core.render import FFMPEG, render_to_file
    from app.core.storage import storage
    from app.models.system import AssetFile
    from app.models.video import VideoAsset
    from app.services.video import _resolve_render_inputs

    target, key = str(job_id), "video_job"
    if not await _claim("render", target, key):
        return {"skipped": True}
    try:
        async with AsyncSessionLocal() as db:
            job = await db.get(VideoJob, job_id)
            if job is None:
                raise ValueError(f"任务不存在：{job_id}")
            job.status = "running"
            job.progress = 30
            await db.commit()

            request = job.request or {}
            resolution = request.get("resolution", "1080x1920")
            fps = int(request.get("fps", 30))
            source_path, segments = await _resolve_render_inputs(db, job.project_id)
            output_key = storage.build_key("render-output", job.project_id, f"final-{job.id}.mp4")
            output_path = storage.local_path(output_key)

            if FFMPEG is None:
                result = {
                    "output_key": output_key,
                    "duration_ms": 30000,
                    "status": "placeholder",
                }
            else:
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
                db.add(VideoAsset(project_id=job.project_id, kind="final", asset_file_id=asset.id))
                result = {
                    "output_key": output_key,
                    "url": f"/media/{output_key}",
                    "duration_ms": duration_ms,
                    "status": "rendered",
                    "segments": len(segments),
                }

            job.result = result
            job.status = "succeeded"
            job.progress = 100
            await db.commit()
        await _settle("render", target, key, result)
        return result
    except Exception as exc:  # noqa: BLE001
        await _settle("render", target, key, {}, str(exc))
        raise
