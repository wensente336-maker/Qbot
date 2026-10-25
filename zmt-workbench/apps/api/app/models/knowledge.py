"""知识卡片相关模型。

二维码：knowledge_cards / knowledge_card_versions / knowledge_sources。
"""

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class KnowledgeCard(Base):
    __tablename__ = "knowledge_cards"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str | None] = mapped_column(Text)
    viewpoint: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ai_generated")
    is_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class KnowledgeCardVersion(Base):
    __tablename__ = "knowledge_card_versions"
    __table_args__ = (
        UniqueConstraint("card_id", "version", name="uq_kcard_versions_card_version"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    card_id: Mapped[int] = mapped_column(ForeignKey("knowledge_cards.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[dict] = mapped_column(JSON, nullable=False)  # 全量快照
    diff: Mapped[dict | None] = mapped_column(JSON)  # 与上一版差异
    source: Mapped[str] = mapped_column(String(16), nullable=False)  # ai / human
    model: Mapped[str | None] = mapped_column(String(64))
    prompt_version: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class KnowledgeSource(Base):
    __tablename__ = "knowledge_sources"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    card_id: Mapped[int] = mapped_column(ForeignKey("knowledge_cards.id"), nullable=False)
    work_id: Mapped[int] = mapped_column(ForeignKey("source_works.id"), nullable=False)
    relation: Mapped[str] = mapped_column(String(16), nullable=False)  # support/supplement/oppose
    excerpt: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
