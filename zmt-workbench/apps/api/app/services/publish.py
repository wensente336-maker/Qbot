"""发布 / 指标 / 成本 / 配额服务。"""

from datetime import UTC, date, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm import llm
from app.models.project import ContentProject
from app.models.publish import MetricDimension, MetricSnapshot, Publication
from app.models.system import CostEvent, DailyQuota
from app.schemas.publish import CostEventCreate, MetricSyncRequest, PublicationCreate
from app.services.billing import record_llm_usage

DEFAULT_DIMENSIONS = [
    {
        "key": "views",
        "name": "播放量",
        "unit": "次",
        "caliber": "去重后有效播放",
        "source": "douyin",
    },
    {"key": "likes", "name": "点赞", "unit": "次", "caliber": "累计点赞", "source": "douyin"},
    {"key": "comments", "name": "评论", "unit": "条", "caliber": "累计评论", "source": "douyin"},
    {"key": "shares", "name": "转发", "unit": "次", "caliber": "累计转发", "source": "douyin"},
    {
        "key": "followers",
        "name": "涨粉",
        "unit": "人",
        "caliber": "作品带来的新增粉丝",
        "source": "douyin",
    },
]


async def seed_metric_dimensions(db: AsyncSession) -> dict[str, MetricDimension]:
    """确保默认指标口径存在，返回 {key: MetricDimension}。"""
    existing = (await db.scalars(select(MetricDimension))).all()
    by_key = {d.key: d for d in existing}
    for item in DEFAULT_DIMENSIONS:
        if item["key"] not in by_key:
            dim = MetricDimension(**item)
            db.add(dim)
            by_key[item["key"]] = dim
    await db.commit()
    return by_key


async def _get_owned_project(db: AsyncSession, project_id: int, user_id: int) -> ContentProject:
    project = await db.get(ContentProject, project_id)
    if project is None or project.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "项目不存在")
    return project


async def create_publication(
    db: AsyncSession, user_id: int, payload: PublicationCreate
) -> Publication:
    await _get_owned_project(db, payload.project_id, user_id)
    pub = Publication(
        project_id=payload.project_id,
        platform=payload.platform,
        platform_video_id=payload.platform_video_id,
        publish_url=payload.publish_url,
    )
    db.add(pub)
    await db.commit()
    await db.refresh(pub)
    return pub


async def mark_published(db: AsyncSession, user_id: int, publication_id: int) -> Publication:
    pub = await db.get(Publication, publication_id)
    if pub is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "发布记录不存在")
    await _get_owned_project(db, pub.project_id, user_id)
    pub.published_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(pub)
    return pub


async def sync_metrics(
    db: AsyncSession, user_id: int, payload: MetricSyncRequest
) -> list[MetricSnapshot]:
    pub = await db.get(Publication, payload.publication_id)
    if pub is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "发布记录不存在")
    await _get_owned_project(db, pub.project_id, user_id)

    dims = await seed_metric_dimensions(db)
    values = payload.values or {k: 0 for k in DEFAULT_DIMENSIONS if k in dims}

    snapshots: list[MetricSnapshot] = []
    for key, value in values.items():
        dim = dims.get(key)
        if dim is None:
            continue
        snap = MetricSnapshot(
            publication_id=pub.id,
            project_id=pub.project_id,
            dimension_id=dim.id,
            value=int(value),
            stat_date=payload.stat_date,
            source="douyin" if payload.values else "placeholder",
        )
        db.add(snap)
        snapshots.append(snap)

    await db.commit()
    for s in snapshots:
        await db.refresh(s)
    return snapshots


async def list_metrics_for_project(db: AsyncSession, user_id: int, project_id: int) -> list[dict]:
    await _get_owned_project(db, project_id, user_id)
    rows = await db.execute(
        select(
            MetricDimension.key,
            MetricDimension.name,
            func.coalesce(func.sum(MetricSnapshot.value), 0),
        )
        .join(MetricSnapshot, MetricSnapshot.dimension_id == MetricDimension.id)
        .where(MetricSnapshot.project_id == project_id)
        .group_by(MetricDimension.key, MetricDimension.name)
    )
    return [{"key": k, "name": n, "total": int(v)} for k, n, v in rows.all()]


async def record_cost(db: AsyncSession, payload: CostEventCreate) -> CostEvent:
    event = CostEvent(**payload.model_dump())
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return event


async def dashboard(db: AsyncSession, user_id: int) -> dict:
    project_count = await db.scalar(
        select(func.count(ContentProject.id)).where(ContentProject.user_id == user_id)
    )
    published_count = await db.scalar(
        select(func.count(Publication.id))
        .join(ContentProject, ContentProject.id == Publication.project_id)
        .where(ContentProject.user_id == user_id)
    )
    total_views = await db.scalar(
        select(func.coalesce(func.sum(MetricSnapshot.value), 0))
        .join(MetricDimension, MetricDimension.id == MetricSnapshot.dimension_id)
        .join(ContentProject, ContentProject.id == MetricSnapshot.project_id)
        .where(ContentProject.user_id == user_id, MetricDimension.key == "views")
    )
    return {
        "project_count": int(project_count or 0),
        "published_count": int(published_count or 0),
        "total_views": int(total_views or 0),
    }


async def weekly_report(db: AsyncSession, user_id: int, project_id: int | None = None) -> dict:
    since = datetime.now(UTC) - timedelta(days=7)
    q = (
        select(
            MetricDimension.key,
            func.coalesce(func.sum(MetricSnapshot.value), 0),
        )
        .join(MetricDimension, MetricDimension.id == MetricSnapshot.dimension_id)
        .join(ContentProject, ContentProject.id == MetricSnapshot.project_id)
        .where(ContentProject.user_id == user_id, MetricSnapshot.created_at >= since)
    )
    if project_id is not None:
        q = q.where(MetricSnapshot.project_id == project_id)
    rows = await db.execute(q.group_by(MetricDimension.key))
    metrics = {k: int(v) for k, v in rows.all()}

    return {
        "period": "last_7_days",
        "metrics": metrics,
        "summary": await _weekly_summary(db, metrics, project_id),
    }


def _fallback_weekly_summary(metrics: dict[str, int]) -> str:
    """无 LLM 或调用失败时，用指标本身给出可读结论。"""
    if not metrics:
        return "近 7 天暂无指标数据：请先发布作品并同步播放与互动数据。"

    views = metrics.get("views", 0)
    likes = metrics.get("likes", 0)
    comments = metrics.get("comments", 0)
    shares = metrics.get("shares", 0)
    followers = metrics.get("followers", 0)

    parts = [
        f"播放 {views}",
        f"点赞 {likes}",
        f"评论 {comments}",
        f"转发 {shares}",
        f"涨粉 {followers}",
    ]
    if views > 0:
        engagement = (likes + comments + shares) / views * 100
        verdict = (
            "互动率健康，可复用当前选题与开场结构"
            if engagement >= 5
            else "互动率偏低，建议强化前 3 秒钩子与结尾互动引导"
        )
        return f"近 7 天累计{'、'.join(parts)}；互动率 {engagement:.1f}%，{verdict}。"
    return f"近 7 天累计{'、'.join(parts)}；暂无播放数据，先确认作品是否已发布并同步指标。"


async def _weekly_summary(
    db: AsyncSession, metrics: dict[str, int], project_id: int | None
) -> str:
    if llm.mock_enabled:
        return _fallback_weekly_summary(metrics)

    system = (
        "你是短视频数据分析师。基于近 7 天指标输出中文周报结论，"
        "包含：表现概述、可能的增长或下滑原因、下周 2 条可执行建议。"
        "只输出 JSON：{\"summary\": \"...\"}，150 字以内。"
    )
    user = f"项目：{project_id or '全部'}\n指标：{metrics}"
    try:
        data = await llm.json(system, user)
        await record_llm_usage(db, project_id=project_id)
    except Exception:  # noqa: BLE001 - 网络/解析失败时退回本地结论
        return _fallback_weekly_summary(metrics)

    summary = str(data.get("summary") or "").strip()
    return summary or _fallback_weekly_summary(metrics)


async def get_quota(db: AsyncSession, category: str) -> DailyQuota:
    today = date.today()
    q = await db.scalar(
        select(DailyQuota).where(DailyQuota.category == category, DailyQuota.quota_date == today)
    )
    if q is None:
        q = DailyQuota(category=category, quota_date=today, used=0, quota_limit=0)
        db.add(q)
        await db.commit()
        await db.refresh(q)
    return q


async def consume_quota(db: AsyncSession, category: str, amount: int = 1) -> DailyQuota:
    q = await get_quota(db, category)
    q.used += amount
    await db.commit()
    await db.refresh(q)
    return q
