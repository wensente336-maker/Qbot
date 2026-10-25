"""选题路由：生成 + 列表。"""

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.topic import Topic
from app.models.user import User
from app.schemas.topic import TopicGenerateRequest, TopicRead
from app.services.topic import generate_topics

router = APIRouter(prefix="/topics", tags=["topics"])


@router.get("", response_model=list[TopicRead])
async def list_topics(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[Topic]:
    result = await db.scalars(
        select(Topic).where(Topic.user_id == current_user.id).order_by(Topic.created_at.desc())
    )
    return list(result)


@router.post("/generate", response_model=list[TopicRead], status_code=status.HTTP_201_CREATED)
async def create_topics(
    payload: TopicGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Topic]:
    return await generate_topics(db, current_user.id, payload)
