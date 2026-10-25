"""知识卡片路由：生成/列表/锁定/追加来源。"""

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.knowledge import KnowledgeCard, KnowledgeSource
from app.models.user import User
from app.schemas.knowledge import (
    KnowledgeCardGenerate,
    KnowledgeCardLock,
    KnowledgeCardRead,
    KnowledgeSourceCreate,
    KnowledgeSourceRead,
)
from app.services.knowledge import add_source, generate_card, set_locked

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.get("/cards", response_model=list[KnowledgeCardRead])
async def list_cards(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[KnowledgeCard]:
    result = await db.scalars(select(KnowledgeCard).order_by(KnowledgeCard.updated_at.desc()))
    return list(result)


@router.post("/cards", response_model=KnowledgeCardRead, status_code=status.HTTP_201_CREATED)
async def create_card(
    payload: KnowledgeCardGenerate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeCard:
    return await generate_card(db, payload.source_work_ids)


@router.post("/cards/{card_id}/lock", response_model=KnowledgeCardRead)
async def lock_card(
    card_id: int,
    payload: KnowledgeCardLock,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeCard:
    return await set_locked(db, card_id, payload.is_locked)


@router.get("/cards/{card_id}/sources", response_model=list[KnowledgeSourceRead])
async def list_sources(
    card_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[KnowledgeSource]:
    result = await db.scalars(select(KnowledgeSource).where(KnowledgeSource.card_id == card_id))
    return list(result)


@router.post(
    "/cards/{card_id}/sources",
    response_model=KnowledgeSourceRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_card_source(
    card_id: int,
    payload: KnowledgeSourceCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeSource:
    return await add_source(db, card_id, payload.work_id, payload.relation, payload.excerpt)
