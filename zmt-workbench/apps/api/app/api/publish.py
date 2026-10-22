"""发布与指标路由。"""

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.project import ContentProject
from app.models.publish import MetricDimension, Publication
from app.models.user import User
from app.schemas.publish import (
    MetricDimensionRead,
    MetricSyncRequest,
    PublicationCreate,
    PublicationRead,
)
from app.services.publish import (
    create_publication,
    list_metrics_for_project,
    mark_published,
    seed_metric_dimensions,
    sync_metrics,
)

router = APIRouter(tags=["publish"])


@router.get("/publications", response_model=list[PublicationRead])
async def list_publications(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[Publication]:
    result = await db.scalars(
        select(Publication)
        .join(ContentProject, ContentProject.id == Publication.project_id)
        .where(ContentProject.user_id == current_user.id)
        .order_by(Publication.created_at.desc())
    )
    return list(result)


@router.post("/publications", response_model=PublicationRead, status_code=status.HTTP_201_CREATED)
async def add_publication(
    payload: PublicationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Publication:
    return await create_publication(db, current_user.id, payload)


@router.post("/publications/{publication_id}/publish", response_model=PublicationRead)
async def publish(
    publication_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Publication:
    return await mark_published(db, current_user.id, publication_id)


@router.get("/metrics/dimensions", response_model=list[MetricDimensionRead])
async def list_dimensions(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[MetricDimension]:
    await seed_metric_dimensions(db)
    result = await db.scalars(select(MetricDimension).order_by(MetricDimension.id))
    return list(result)


@router.post("/metrics/sync")
async def sync(
    payload: MetricSyncRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    snapshots = await sync_metrics(db, current_user.id, payload)
    return {"synced": len(snapshots), "snapshots": [s.id for s in snapshots]}


@router.get("/metrics/{project_id}")
async def metrics(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    return await list_metrics_for_project(db, current_user.id, project_id)
