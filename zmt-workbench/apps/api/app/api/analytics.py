"""驾驶舱 / 周报 / 成本 / 配额路由。"""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.system import CostEvent, DailyQuota
from app.models.user import User
from app.schemas.publish import CostEventCreate, CostEventRead, QuotaRead
from app.services.publish import consume_quota, dashboard, get_quota, record_cost, weekly_report

router = APIRouter(tags=["analytics"])


@router.get("/dashboard")
async def get_dashboard(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    return await dashboard(db, current_user.id)


@router.get("/weekly-report")
async def get_weekly_report(
    project_id: int | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await weekly_report(db, current_user.id, project_id)


@router.post("/costs", response_model=CostEventRead, status_code=status.HTTP_201_CREATED)
async def add_cost(
    payload: CostEventCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CostEvent:
    return await record_cost(db, payload)


@router.get("/costs", response_model=list[CostEventRead])
async def list_costs(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[CostEvent]:
    result = await db.scalars(select(CostEvent).order_by(CostEvent.created_at.desc()))
    return list(result)


@router.get("/quota/{category}", response_model=QuotaRead)
async def quota(
    category: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DailyQuota:
    return await get_quota(db, category)


@router.post("/quota/{category}/consume", response_model=QuotaRead)
async def quota_consume(
    category: str,
    amount: int = Query(default=1, ge=1),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DailyQuota:
    return await consume_quota(db, category, amount)
