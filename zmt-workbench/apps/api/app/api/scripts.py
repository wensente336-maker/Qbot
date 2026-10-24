"""文案路由：大纲（生成/审批）、脚本（生成/局部重写/版本）。"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.script import Outline, Script, ScriptVersion
from app.models.user import User
from app.schemas.script import (
    OutlineApprove,
    OutlineGenerate,
    OutlineRead,
    ScriptGenerate,
    ScriptRead,
    ScriptVersionRead,
    SegmentRewrite,
)
from app.services.script import (
    approve_outline,
    generate_outline,
    generate_script,
    rewrite_segment,
)

router = APIRouter(tags=["scripts"])


@router.post("/outlines/generate", response_model=OutlineRead, status_code=status.HTTP_201_CREATED)
async def create_outline(
    payload: OutlineGenerate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Outline:
    return await generate_outline(db, payload.project_id, current_user.id)


@router.get("/outlines/{project_id}", response_model=OutlineRead)
async def get_outline(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Outline:
    outline = await db.scalar(
        select(Outline).where(Outline.project_id == project_id).order_by(Outline.version.desc())
    )
    if outline is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "尚未生成大纲")
    return outline


@router.post("/outlines/{project_id}/approve", response_model=OutlineRead)
async def approve(
    project_id: int,
    payload: OutlineApprove,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Outline:
    return await approve_outline(db, project_id, current_user.id, payload.approved)


@router.post("/scripts/generate", response_model=ScriptRead, status_code=status.HTTP_201_CREATED)
async def create_script(
    payload: ScriptGenerate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Script:
    return await generate_script(
        db, payload.project_id, current_user.id, payload.skill, payload.intensity, payload.length
    )


@router.get("/scripts/{project_id}", response_model=ScriptRead)
async def get_script(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Script:
    script = await db.scalar(select(Script).where(Script.project_id == project_id))
    if script is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "尚未生成文案")
    return script


@router.post("/scripts/{script_id}/rewrite", response_model=ScriptRead)
async def rewrite(
    script_id: int,
    payload: SegmentRewrite,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Script:
    return await rewrite_segment(
        db, script_id, current_user.id, payload.segment, payload.instruction
    )


@router.get("/scripts/{script_id}/versions", response_model=list[ScriptVersionRead])
async def list_versions(
    script_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ScriptVersion]:
    result = await db.scalars(
        select(ScriptVersion)
        .where(ScriptVersion.script_id == script_id)
        .order_by(ScriptVersion.version.desc())
    )
    return list(result)
