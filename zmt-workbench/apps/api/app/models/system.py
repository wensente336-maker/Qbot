"""系统支撑模型：文件、任务审计、操作日志、成本、配额。

二维码：asset_files / task_runs / audit_logs / cost_events / daily_quotas。
"""

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AssetFile(Base):
    """文件对象统一建模（COS 桶 + key + 生命周期）。"""

    __tablename__ = "asset_files"
    __table_args__ = (Index("ix_asset_files_lifecycle", "lifecycle", "expires_at"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    bucket: Mapped[str] = mapped_column(String(64), nullable=False)
    key: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str | None] = mapped_column(Text)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    content_type: Mapped[str | None] = mapped_column(String(64))
    lifecycle: Mapped[str] = mapped_column(String(16), nullable=False, default="temporary")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="uploaded")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class TaskRun(Base):
    """通用任务审计（幂等键 task_type + target_id + run_key）。"""

    __tablename__ = "task_runs"
    __table_args__ = (
        UniqueConstraint("task_type", "target_id", "run_key", name="uq_task_runs_idempotency"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    task_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[str] = mapped_column(String(64), nullable=False)
    run_key: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    payload: Mapped[dict | None] = mapped_column(JSON)
    result: Mapped[dict | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    entity_type: Mapped[str | None] = mapped_column(String(32))
    entity_id: Mapped[str | None] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    detail: Mapped[dict | None] = mapped_column(JSON)
    ip: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CostEvent(Base):
    """成本分项记账（asr/llm/render/storage/traffic）。"""

    __tablename__ = "cost_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(String(16), nullable=False)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("content_projects.id"))
    job_id: Mapped[int | None] = mapped_column(ForeignKey("video_jobs.id"))
    vendor: Mapped[str | None] = mapped_column(String(64))
    model: Mapped[str | None] = mapped_column(String(64))
    units: Mapped[float | None] = mapped_column(Numeric(18, 4))
    unit_price: Mapped[float | None] = mapped_column(Numeric(18, 6))
    cost: Mapped[float | None] = mapped_column(Numeric(18, 6))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class DailyQuota(Base):
    """单日配额计数。"""

    __tablename__ = "daily_quotas"
    __table_args__ = (
        UniqueConstraint("category", "quota_date", name="uq_daily_quotas_category_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(String(16), nullable=False)
    quota_date: Mapped[date] = mapped_column(Date, nullable=False)
    used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    quota_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
