"""视频链路路由：转写/粗剪/分镜/渲染/质检/任务列表。"""

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.models.video import VideoJob
from app.schemas.video import (
    RenderRequest,
    RoughCutRequest,
    StoryboardRequest,
    TranscribeRequest,
    VideoJobRead,
)
from app.services.video import (
    generate_storyboard,
    render_video,
    rough_cut,
    run_qa,
    transcribe_video,
)

router = APIRouter(prefix="/videos", tags=["videos"])


@router.get("/{project_id}/jobs", response_model=list[VideoJobRead])
async def list_jobs(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[VideoJob]:
    result = await db.scalars(
        select(VideoJob)
        .where(VideoJob.project_id == project_id)
        .order_by(VideoJob.created_at.desc())
    )
    return list(result)


@router.post(
    "/{project_id}/transcribe", response_model=VideoJobRead, status_code=status.HTTP_201_CREATED
)
async def transcribe(
    project_id: int,
    payload: TranscribeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> VideoJob:
    return await transcribe_video(db, current_user.id, project_id, payload.asset_ref)


@router.post(
    "/{project_id}/rough-cut", response_model=VideoJobRead, status_code=status.HTTP_201_CREATED
)
async def cut(
    project_id: int,
    payload: RoughCutRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> VideoJob:
    return await rough_cut(db, current_user.id, project_id, payload.cuts)


@router.post(
    "/{project_id}/storyboard", response_model=VideoJobRead, status_code=status.HTTP_201_CREATED
)
async def storyboard(
    project_id: int,
    payload: StoryboardRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> VideoJob:
    return await generate_storyboard(db, current_user.id, project_id, payload.script_id)


@router.post(
    "/{project_id}/render", response_model=VideoJobRead, status_code=status.HTTP_201_CREATED
)
async def render(
    project_id: int,
    payload: RenderRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> VideoJob:
    return await render_video(
        db,
        current_user.id,
        project_id,
        payload.composition,
        payload.resolution,
        payload.fps,
    )


@router.post("/jobs/{job_id}/qa", response_model=VideoJobRead)
async def qa(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> VideoJob:
    return await run_qa(db, current_user.id, job_id)
