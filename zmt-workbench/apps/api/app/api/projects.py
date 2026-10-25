"""内容项目路由：列表 / 创建 / 状态机流转。"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.project import ContentProject
from app.models.user import User
from app.schemas.project import (
    PROJECT_STATUSES,
    STATUS_ORDER,
    ContentProjectCreate,
    ContentProjectRead,
    ContentProjectUpdate,
)

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[ContentProjectRead])
async def list_projects(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[ContentProject]:
    result = await db.scalars(
        select(ContentProject)
        .where(ContentProject.user_id == current_user.id)
        .order_by(ContentProject.updated_at.desc())
    )
    return list(result)


@router.post("", response_model=ContentProjectRead, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ContentProjectCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ContentProject:
    project = ContentProject(topic_id=payload.topic_id, user_id=current_user.id)
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


@router.patch("/{project_id}", response_model=ContentProjectRead)
async def update_status(
    project_id: int,
    payload: ContentProjectUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ContentProject:
    project = await db.get(ContentProject, project_id)
    if project is None or project.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "项目不存在")

    if payload.status not in STATUS_ORDER:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"非法状态，合法值为：{', '.join(PROJECT_STATUSES)}",
        )
    # 状态机约束：仅允许逐步向前推进（+1），不允许跳步或回退
    if STATUS_ORDER[payload.status] != STATUS_ORDER[project.status] + 1:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"只允许从「{project.status}」推进到下一阶段",
        )

    project.status = payload.status
    await db.commit()
    await db.refresh(project)
    return project
