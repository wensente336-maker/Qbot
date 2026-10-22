"""初始迁移：创建全部 26 张业务表。

Revision ID: 0001
Revises:
Create Date: 2026-10-22
"""

import app.models  # noqa: F401  # 注册全部 ORM 模型
from alembic import op
from app.db.base import Base

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """基于 ORM metadata 一次性建表（引导迁移）。"""
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    """回滚：删除全部表。"""
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
