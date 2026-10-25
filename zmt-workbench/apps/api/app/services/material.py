"""素材服务：录入素材 + AI 特征提取（版本化）。"""

import json
import re

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.llm import llm
from app.models.benchmark import Creator, MaterialFeature, SourceWork
from app.schemas.material import SourceWorkCreate
from app.services.billing import record_llm_usage
from app.services.quota import ensure_quota

_FEATURE_SEPARATORS = re.compile(r"[,，、;；/\n|]+")


def _normalize_features(value: object) -> list[str] | None:
    """把 LLM 返回的 features 统一成 list[str]。

    DeepSeek 在 JSON 模式下仍可能返回字符串（「标签A、标签B」）或对象数组，
    直接入库会与 `MaterialFeatureRead.features: list` 冲突，因此在此收敛。
    """
    if value is None:
        return None
    if isinstance(value, str):
        items = [part.strip() for part in _FEATURE_SEPARATORS.split(value)]
        return [item for item in items if item] or None
    if isinstance(value, (list, tuple, set)):
        result: list[str] = []
        for item in value:
            if isinstance(item, str):
                text = item.strip()
            elif isinstance(item, dict):
                text = str(
                    item.get("label") or item.get("name") or item.get("tag") or ""
                ).strip()
            else:
                text = str(item).strip()
            if text and text not in result:
                result.append(text)
        return result or None
    text = str(value).strip()
    return [text] if text else None


def _as_text(value: object) -> str | None:
    """把可能为数组/对象的字段收敛为文本，避免写库类型错误。"""
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, (list, tuple)):
        return "、".join(str(v).strip() for v in value if str(v).strip()) or None
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return str(value).strip() or None


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
        await ensure_quota(db, "llm", 0)
        system = "你是短视频素材分析专家，输出 JSON 字段：theme/audience/core_viewpoint/hook/structure/emotion/features。"
        user = f"素材标题：{work.title or ''}\n文案：{work.caption or ''}"
        data = await llm.json(system, user)
        await record_llm_usage(db)
        model = settings.llm_model

    feat = MaterialFeature(
        work_id=work_id,
        version=version,
        theme=_as_text(data.get("theme")),
        audience=_as_text(data.get("audience")),
        core_viewpoint=_as_text(data.get("core_viewpoint")),
        hook=_as_text(data.get("hook")),
        structure=_as_text(data.get("structure")),
        emotion=_as_text(data.get("emotion")),
        features=_normalize_features(data.get("features")),
        model=model,
    )
    db.add(feat)
    await db.commit()
    await db.refresh(feat)
    return feat
