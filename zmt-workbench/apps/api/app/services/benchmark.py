"""对标监测服务：遍历启用的监测账号，增量拉取并入库 source_works。

真实拉取走 `douyin_source.list_works`（无 token/API 时为占位）；本模块负责「遍历账号 +
字段归一化 + (platform, work_id) 去重 + last_checked_at 更新」的完整入库逻辑，
接入抖音开放平台后无需改动即可打通。
"""

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.datasource import douyin_source
from app.models.benchmark import BenchmarkAccount, Creator, SourceWork

logger = logging.getLogger(__name__)


def _normalize_work(work: dict) -> dict:
    """将上游作品字段归一化为 SourceWork 入库字段。"""
    work_id = (
        work.get("work_id")
        or work.get("aweme_id")
        or work.get("item_id")
        or work.get("id")
        or ""
    )
    published_raw = work.get("published_at") or work.get("create_time") or work.get("pub_time")
    if isinstance(published_raw, (int, float)):
        published_at = datetime.fromtimestamp(int(published_raw), tz=UTC)
    elif isinstance(published_raw, str) and published_raw.isdigit():
        published_at = datetime.fromtimestamp(int(published_raw), tz=UTC)
    else:
        published_at = None

    return {
        "work_id": str(work_id),
        "title": work.get("title") or work.get("desc") or work.get("caption"),
        "cover_url": work.get("cover_url") or work.get("cover"),
        "source_url": work.get("source_url") or work.get("share_url") or work.get("url"),
        "caption": work.get("caption") or work.get("desc"),
        "published_at": published_at,
    }


async def _upsert_source_work(db: AsyncSession, creator: Creator, normalized: dict) -> SourceWork | None:
    """按 (platform, work_id) 去重入库；已存在返回 None（增量跳过）。"""
    if not normalized["work_id"]:
        return None
    exists = await db.scalar(
        select(SourceWork).where(
            SourceWork.platform == creator.platform,
            SourceWork.work_id == normalized["work_id"],
        )
    )
    if exists is not None:
        return None
    work = SourceWork(creator_id=creator.id, platform=creator.platform, **normalized)
    db.add(work)
    await db.flush()
    return work


async def sync_benchmark(db: AsyncSession) -> dict:
    """遍历启用的对标账号，增量拉取并入库作品，返回统计信息。"""
    if not douyin_source.enabled:
        logger.warning("抖音数据源未授权，sync_benchmark 跳过")
        return {"scanned": 0, "created": 0, "reason": "douyin_not_authorized"}

    accounts = (
        await db.scalars(select(BenchmarkAccount).where(BenchmarkAccount.enabled.is_(True)))
    ).all()

    scanned = 0
    created = 0
    for account in accounts:
        creator = await db.get(Creator, account.creator_id)
        if creator is None:
            continue
        scanned += 1
        try:
            works = await douyin_source.list_works(
                creator.platform_uid, limit=account.first_study_limit
            )
        except NotImplementedError:
            # API 占位：接入真实 API 后自然连通
            continue
        for w in works or []:
            normalized = _normalize_work(w)
            if await _upsert_source_work(db, creator, normalized) is not None:
                created += 1
        account.last_checked_at = datetime.now(UTC)

    await db.commit()
    return {"scanned": scanned, "created": created}
