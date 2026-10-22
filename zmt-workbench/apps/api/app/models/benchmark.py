"""对标监测相关模型：创作者、监测配置、作品、转写、素材特征。

二维码：creators / benchmark_accounts / source_works / transcripts / material_features。
"""

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Creator(Base):
    """第三方创作者档案（抖音博主）。"""

    __tablename__ = "creators"
    __table_args__ = (
        UniqueConstraint("platform", "platform_uid", name="uq_creators_platform_uid"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    platform: Mapped[str] = mapped_column(String(16), nullable=False, default="douyin")
    platform_uid: Mapped[str] = mapped_column(String(128), nullable=False)
    nickname: Mapped[str | None] = mapped_column(String(128))
    avatar_url: Mapped[str | None] = mapped_column(Text)
    homepage_url: Mapped[str | None] = mapped_column(Text)
    bio: Mapped[str | None] = mapped_column(Text)


class BenchmarkAccount(Base):
    """对标监测配置（一个用户可监测多个账号）。"""

    __tablename__ = "benchmark_accounts"
    __table_args__ = (UniqueConstraint("user_id", "creator_id", name="uq_benchmark_user_creator"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    creator_id: Mapped[int] = mapped_column(ForeignKey("creators.id"), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    check_interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=720)
    first_study_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SourceWork(Base):
    """对标作品（按 platform + work_id 去重）。"""

    __tablename__ = "source_works"
    __table_args__ = (
        UniqueConstraint("platform", "work_id", name="uq_source_works_platform_work"),
        Index("ix_source_works_creator", "creator_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey("creators.id"), nullable=False)
    platform: Mapped[str] = mapped_column(String(16), nullable=False, default="douyin")
    work_id: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    cover_url: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    author_name: Mapped[str | None] = mapped_column(String(128))
    caption: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    parse_status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    parse_error: Mapped[str | None] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Transcript(Base):
    """转写结果（词级时间轴以 JSON 存储）。"""

    __tablename__ = "transcripts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    work_id: Mapped[int | None] = mapped_column(ForeignKey("source_works.id"))
    content: Mapped[str | None] = mapped_column(Text)
    words: Mapped[list | None] = mapped_column(JSON)  # [{word, start, end}]
    model: Mapped[str | None] = mapped_column(String(64))
    language: Mapped[str] = mapped_column(String(16), nullable=False, default="zh")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class MaterialFeature(Base):
    """素材 AI 特征分析（1:N 版本化，保留历史）。"""

    __tablename__ = "material_features"
    __table_args__ = (
        UniqueConstraint("work_id", "version", name="uq_material_features_work_version"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    work_id: Mapped[int] = mapped_column(ForeignKey("source_works.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    theme: Mapped[str | None] = mapped_column(Text)
    audience: Mapped[str | None] = mapped_column(Text)
    core_viewpoint: Mapped[str | None] = mapped_column(Text)
    hook: Mapped[str | None] = mapped_column(Text)
    structure: Mapped[str | None] = mapped_column(Text)
    emotion: Mapped[str | None] = mapped_column(Text)
    features: Mapped[list | None] = mapped_column(JSON)  # 多标签分类
    analysis: Mapped[str | None] = mapped_column(Text)
    model: Mapped[str | None] = mapped_column(String(64))
    prompt_version: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
