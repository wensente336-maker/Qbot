"""素材路由：录入/列表 + AI 特征提取（版本化）。"""

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.benchmark import MaterialFeature, SourceWork
from app.models.user import User
from app.schemas.material import (
    FeatureExtractRequest,
    MaterialFeatureRead,
    SourceWorkCreate,
    SourceWorkRead,
)
from app.services.material import create_source_work, extract_features

router = APIRouter(prefix="/materials", tags=["materials"])


@router.get("", response_model=list[SourceWorkRead])
async def list_materials(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[SourceWork]:
    result = await db.scalars(select(SourceWork).order_by(SourceWork.discovered_at.desc()))
    return list(result)


@router.post("", response_model=SourceWorkRead, status_code=status.HTTP_201_CREATED)
async def add_material(
    payload: SourceWorkCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SourceWork:
    return await create_source_work(db, payload)


@router.post("/feature-extract", response_model=MaterialFeatureRead)
async def feature_extract(
    payload: FeatureExtractRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MaterialFeature:
    return await extract_features(db, payload.work_id)


@router.get("/{work_id}/features", response_model=list[MaterialFeatureRead])
async def list_features(
    work_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[MaterialFeature]:
    result = await db.scalars(
        select(MaterialFeature)
        .where(MaterialFeature.work_id == work_id)
        .order_by(MaterialFeature.version.desc())
    )
    return list(result)
