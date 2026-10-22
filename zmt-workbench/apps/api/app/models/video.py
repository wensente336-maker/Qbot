"""视频与视觉相关模型。

二维码：video_assets / video_jobs / visual_skills。
"""

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class VideoAsset(Base):
    __tablename__ = "video_assets"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("content_projects.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # source/intermediate/final
    asset_file_id: Mapped[int] = mapped_column(ForeignKey("asset_files.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class VideoJob(Base):
    __tablename__ = "video_jobs"
    __table_args__ = (Index("ix_video_jobs_project", "project_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("content_projects.id"), nullable=False)
    job_type: Mapped[str] = mapped_column(
        String(24), nullable=False
    )  # transcribe/editing/render/export
    request: Mapped[dict | None] = mapped_column(JSON)  # 参数 + 时间轴映射表
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued")
    result: Mapped[dict | None] = mapped_column(JSON)  # 质检结果 / 输出信息
    error: Mapped[str | None] = mapped_column(Text)
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class VisualSkill(Base):
    __tablename__ = "visual_skills"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
