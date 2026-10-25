"""知识卡片服务：观点聚合 + 人工锁定 + 版本 + 溯源。"""

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.llm import llm
from app.models.knowledge import KnowledgeCard, KnowledgeCardVersion, KnowledgeSource
from app.services.billing import record_llm_usage
from app.services.quota import ensure_quota


async def generate_card(
    db: AsyncSession, source_work_ids: list[int] | None = None
) -> KnowledgeCard:
    """聚合素材观点生成知识卡片（否用 LLM 则有 mock）。"""
    if llm.mock_enabled:
        title, viewpoint = "占位卡片标题", "由素材聚合出的观点（占位）"
        model = "mock"
    else:
        await ensure_quota(db, "llm", 0)
        system = "你是知识卡片整理专家，从素材中提炼观点。输出 JSON：{title, viewpoint}。"
        user = f"素材 ID 列表：{source_work_ids or []}"
        data = await llm.json(system, user)
        await record_llm_usage(db)
        title, viewpoint = data.get("title"), data.get("viewpoint")
        model = settings.llm_model

    card = KnowledgeCard(title=title, viewpoint=viewpoint, status="ai_generated", is_locked=False)
    db.add(card)
    await db.commit()
    await db.refresh(card)

    version = KnowledgeCardVersion(
        card_id=card.id,
        version=1,
        content={"title": title, "viewpoint": viewpoint},
        source="ai",
        model=model,
    )
    db.add(version)

    if source_work_ids:
        for wid in source_work_ids:
            db.add(KnowledgeSource(card_id=card.id, work_id=wid, relation="support"))

    await db.commit()
    await db.refresh(card)
    return card


async def set_locked(db: AsyncSession, card_id: int, is_locked: bool) -> KnowledgeCard:
    card = await db.get(KnowledgeCard, card_id)
    if card is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "卡片不存在")
    card.is_locked = is_locked
    card.status = "locked" if is_locked else "ai_generated"
    await db.commit()
    await db.refresh(card)
    return card


async def add_source(
    db: AsyncSession, card_id: int, work_id: int, relation: str, excerpt: str | None
) -> KnowledgeSource:
    card = await db.get(KnowledgeCard, card_id)
    if card is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "卡片不存在")
    if card.is_locked:
        raise HTTPException(status.HTTP_409_CONFLICT, "卡片已锁定，禁止 AI 覆盖/追加来源")
    src = KnowledgeSource(card_id=card_id, work_id=work_id, relation=relation, excerpt=excerpt)
    db.add(src)
    await db.commit()
    await db.refresh(src)
    return src
