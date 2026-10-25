"""选题服务：双入口生成（theme 主题发散 / benchmark 对标二创）。"""

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm import llm
from app.models.benchmark import SourceWork
from app.models.topic import Topic
from app.schemas.topic import TopicGenerateRequest
from app.services.billing import record_llm_usage
from app.services.quota import ensure_quota


def _mock_angles(count: int, base: str) -> list[dict]:
    """无 LLM 时的占位选题（10 个角度模板）。"""
    return [
        {
            "title": f"{base}｜角度 {i + 1}（占位）",
            "viewpoint": f"从角度 {i + 1} 切入的核心观点（占位）",
            "audience": "目标受众（占位）",
            "angle": f"角度{i + 1}",
            "recommendation": "建议结合对标数据进一步验证（占位）",
        }
        for i in range(count)
    ]


async def generate_topics(
    db: AsyncSession, user_id: int, payload: TopicGenerateRequest
) -> list[Topic]:
    """按入口生成一组选题并落库，返回 Topic 列表。"""
    if payload.entry == "benchmark":
        if payload.source_work_id is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, "benchmark 入口必须提供 source_work_id"
            )
        work = await db.get(SourceWork, payload.source_work_id)
        if work is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "对标素材不存在")
        base = work.title or work.caption or f"素材#{work.id}"
    else:
        if not payload.base_topic:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, "theme 入口必须提供 base_topic"
            )
        base = payload.base_topic

    if llm.mock_enabled:
        angles = _mock_angles(payload.count, base)
        recommendation_base = None
    else:
        await ensure_quota(db, "llm", 0)
        system = (
            "你是短视频选题策划专家。输出 JSON 数组，每项含 "
            "{title, viewpoint, audience, angle, recommendation}。"
        )
        user = f"入口：{payload.entry}\n主题：{base}\n需求数量：{payload.count}"
        angles = await llm.json_list(system, user)
        await record_llm_usage(db)
        recommendation_base = None

    topics: list[Topic] = []
    for a in angles[: payload.count]:
        topic = Topic(
            user_id=user_id,
            entry=payload.entry,
            base_topic=base,
            source_work_id=payload.source_work_id if payload.entry == "benchmark" else None,
            title=a.get("title"),
            viewpoint=a.get("viewpoint"),
            audience=a.get("audience"),
            angle=a.get("angle"),
            recommendation=a.get("recommendation", recommendation_base),
            status="pending",
        )
        db.add(topic)
        topics.append(topic)

    await db.commit()
    for t in topics:
        await db.refresh(t)
    return topics
