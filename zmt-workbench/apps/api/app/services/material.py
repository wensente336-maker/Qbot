"""素材服务：录入素材 + AI 特征提取（版本化）。"""

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.llm import llm
from app.models.benchmark import Creator, MaterialFeature, SourceWork
from app.schemas.material import SourceWorkCreate


async def _get_or_create_placeholder_creator(
    db: AsyncSession, platform: str
) -> Creator:
    """手动录入素材时的占位创作者：按 (platform, "manual") 复用。"""
    uid = "manual"
    creator = await db.scalar(
        select(Creator).where(
            Creator.platform == platform, Creator.platform_uid == uid
        )
    )
    if creator:
        return creator
    creator = Creator(platform=platform, platform_uid=uid, nickname="手动录入")
    db.add(creator)
    await db.flush()
    return creator


async def create_source_work(db: AsyncSession, payload: SourceWorkCreate) -> SourceWork:
    """录入（手动/导入）素材，按 (platform, work_id) 幂等去重。"""
    exists = await db.scalar(
        select(SourceWork).where(
            SourceWork.platform == payload.platform, SourceWork.work_id == payload.work_id
        )
    )
    if exists:
        return exists

    data = payload.model_dump()
    if data.get("creator_id") is None:
        creator = await _get_or_create_placeholder_creator(db, payload.platform)
        data["creator_id"] = creator.id

    work = SourceWork(**data)
    db.add(work)
    await db.commit()
    await db.refresh(work)
    return work


async def extract_features(db: AsyncSession, work_id: int) -> MaterialFeature:
    """对素材做 AI 特征提取，保留历史版本（unique(work_id, version)）。"""
    work = await db.get(SourceWork, work_id)
    if work is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "素材不存在")

    max_v = await db.scalar(
        select(func.max(MaterialFeature.version)).where(MaterialFeature.work_id == work_id)
    )
    version = (max_v or 0) + 1

    if llm.mock_enabled:
        data = {
            "theme": "占位主题",
            "audience": "目标受众（占位）",
            "core_viewpoint": "核心观点（占位）",
            "hook": "开头钩子（占位）",
            "structure": "结构拆解（占位）",
            "emotion": "情绪基调（占位）",
            "features": ["标签A", "标签B"],
        }
        model = "mock"
    else:
        system = "你是短视频素材分析专家，输出 JSON 字段：theme/audience/core_viewpoint/hook/structure/emotion/features。"
        user = f"素材标题：{work.title or ''}\n文案：{work.caption or ''}"
        data = await llm.json(system, user)
        model = settings.llm_model

    feat = MaterialFeature(
        work_id=work_id,
        version=version,
        theme=data.get("theme"),
        audience=data.get("audience"),
        core_viewpoint=data.get("core_viewpoint"),
        hook=data.get("hook"),
        structure=data.get("structure"),
        emotion=data.get("emotion"),
        features=data.get("features"),
        model=model,
    )
    db.add(feat)
    await db.commit()
    await db.refresh(feat)
    return feat
