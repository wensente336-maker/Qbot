"""LLM 成本记账：把最近一次模型调用的 token 用量写入 cost_events 与 daily_quotas。

定价为占位默认值（DeepSeek deepseek-chat：输入 1 元 / 百万 tokens，输出 2 元 / 百万 tokens），
接入真实计费或不同模型时在 LLM_PRICE_PER_M 中补充即可。
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm import llm
from app.models.system import CostEvent
from app.services.quota import add_usage

# 元 / 百万 tokens
LLM_PRICE_PER_M: dict[str, dict[str, float]] = {
    "deepseek-chat": {"input": 1.0, "output": 2.0},
}
DEFAULT_PRICE = {"input": 1.0, "output": 2.0}


async def _bump_daily_quota(db: AsyncSession, category: str, amount: int) -> None:
    """按 token 总量累加当日配额使用计数（不拦截，拦截在调用前由 ensure_quota 完成）。"""
    await add_usage(db, category, amount, commit=False)


async def record_llm_usage(
    db: AsyncSession, project_id: int | None = None, job_id: int | None = None
) -> CostEvent | None:
    """若存在最近一次 LLM 调用的 usage，则写入成本事件并清空缓存。"""
    usage = llm.last_usage
    if not usage:
        return None

    prompt = int(usage.get("prompt_tokens") or 0)
    completion = int(usage.get("completion_tokens") or 0)
    total = prompt + completion
    llm.last_usage = None  # 消费后清空，避免重复记账
    if total == 0:
        return None

    price = LLM_PRICE_PER_M.get(llm.model, DEFAULT_PRICE)
    cost = prompt / 1_000_000 * price["input"] + completion / 1_000_000 * price["output"]

    event = CostEvent(
        category="llm",
        project_id=project_id,
        job_id=job_id,
        vendor="deepseek",
        model=llm.model,
        units=float(total),
        unit_price=float(price["input"]),
        cost=round(cost, 6),
    )
    db.add(event)
    await _bump_daily_quota(db, "llm", total)
    await db.commit()
    await db.refresh(event)
    return event
