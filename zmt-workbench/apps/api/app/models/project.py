"""内容项目模型（状态机主表）。

二维码：content_projects。状态流转顺序见 schemas/project.py 中的 PROJECT_STATUSES。
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ContentProject(Base):
    __tablename__ = "content_projects"
    __table_args__ = (Index("ix_content_projects_status", "status"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    topic_id: Mapped[int | None] = mapped_column(ForeignKey("topics.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="topic_confirmed")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
