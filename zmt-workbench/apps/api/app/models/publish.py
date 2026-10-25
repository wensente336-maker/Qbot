"""发布与指标相关模型。

二维码：publications / metric_dimensions / metric_snapshots。
"""

from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Publication(Base):
    __tablename__ = "publications"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("content_projects.id"), nullable=False)
    platform: Mapped[str] = mapped_column(String(16), nullable=False, default="douyin")
    platform_video_id: Mapped[str | None] = mapped_column(String(128))
    publish_url: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class MetricDimension(Base):
    """指标口径字典（播放/点赞/评论/转发/涨粉）。"""

    __tablename__ = "metric_dimensions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(16))
    caliber: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(String(64))


class MetricSnapshot(Base):
    __tablename__ = "metric_snapshots"
    __table_args__ = (Index("ix_metric_snapshots_project_date", "project_id", "stat_date"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    publication_id: Mapped[int | None] = mapped_column(ForeignKey("publications.id"))
    project_id: Mapped[int] = mapped_column(ForeignKey("content_projects.id"), nullable=False)
    dimension_id: Mapped[int] = mapped_column(ForeignKey("metric_dimensions.id"), nullable=False)
    value: Mapped[int] = mapped_column(BigInteger, nullable=False)
    stat_date: Mapped[date] = mapped_column(Date, nullable=False)
    source: Mapped[str | None] = mapped_column(String(64))
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
