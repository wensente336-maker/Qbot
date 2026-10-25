"""每日配额：限额来自配置，预扣即拦截（超限返回 429）。

类别与单位：
- `llm`        token 数（调用前无法预估，只检查是否还有额度，调用后按实际 token 记账）
- `tts_char`   合成字符数
- `transcribe` 转写次数
- `render`     出片次数

限额按 `QUOTA_LIMITS`（JSON）配置，未配置的类别用内置默认值，填 0 表示不限。
"""

import json
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.system import DailyQuota

DEFAULT_LIMITS: dict[str, int] = {
    "llm": 2_000_000,
    "tts_char": 50_000,
    "transcribe": 30,
    "render": 20,
}


def quota_limits() -> dict[str, int]:
    """当前生效的限额表；配置非法时静默回退默认值，避免拖垮业务。"""
    limits = dict(DEFAULT_LIMITS)
    raw = (settings.quota_limits or "").strip()
    if not raw:
        return limits
    try:
        parsed = json.loads(raw)
    except ValueError:
        return limits
    if not isinstance(parsed, dict):
        return limits
    for key, value in parsed.items():
        try:
            limits[str(key)] = max(0, int(value))
        except (TypeError, ValueError):
            continue
    return limits


def limit_for(category: str) -> int:
    return int(quota_limits().get(category, 0))


async def get_daily(db: AsyncSession, category: str, *, lock: bool = False) -> DailyQuota:
    """取当日配额行，并同步配置中的限额（改配置后下一次调用即生效）。"""
    today = date.today()
    stmt = select(DailyQuota).where(
        DailyQuota.category == category, DailyQuota.quota_date == today
    )
    if lock:
        stmt = stmt.with_for_update()
    q = await db.scalar(stmt)

    limit = limit_for(category)
    if q is None:
        q = DailyQuota(category=category, quota_date=today, used=0, quota_limit=limit)
        db.add(q)
        await db.commit()
        await db.refresh(q)
        return q
    if q.quota_limit != limit:
        q.quota_limit = limit
        await db.commit()
        await db.refresh(q)
    return q


async def ensure_quota(db: AsyncSession, category: str, amount: int = 1) -> DailyQuota:
    """预扣配额；不足则抛 429。

    `amount=0` 只校验是否还有额度、不累加，用于 LLM 这类调用前无法预估消耗量的场景。
    """
    q = await get_daily(db, category, lock=True)
    limit = int(q.quota_limit or 0)
    if limit <= 0:  # 0 = 不限
        if amount > 0:
            q.used += amount
            await db.commit()
            await db.refresh(q)
        return q

    if q.used >= limit or q.used + amount > limit:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"今日 {category} 配额已用尽（{q.used}/{limit}），请明日再试或调整 QUOTA_LIMITS",
        )
    if amount > 0:
        q.used += amount
        await db.commit()
        await db.refresh(q)
    return q


async def add_usage(db: AsyncSession, category: str, amount: int, *, commit: bool = True) -> None:
    """事后记账（不拦截）：用于 LLM 实际 token 这类先消费后统计的量。"""
    if amount <= 0:
        return
    q = await get_daily(db, category)
    q.used += amount
    if commit:
        await db.commit()
    else:
        await db.flush()
