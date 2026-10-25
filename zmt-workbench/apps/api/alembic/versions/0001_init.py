"""初始迁移：逐表创建全部 26 张业务表。

Revision ID: 0001
Revises:
Create Date: 2026-10-22

创建顺序：按外键依赖拓扑排序（被引用表先建），drop 时逆序删除。
约束/索引命名遵循 app.db.base.NAMING_CONVENTION，与 create_all 生成结果一致。
"""

import sqlalchemy as sa

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

# 通用列定义，减少重复
ID = lambda: sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True)  # noqa: E731


def _ts_col(name: str) -> sa.Column:
    """带 timezone、server_default now() 的时间戳列。"""
    return sa.Column(name, sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)


def upgrade() -> None:
    # 1. 无外键依赖的基础表
    op.create_table(
        "users",
        ID(),
        sa.Column("username", sa.String(64), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(20), nullable=True, unique=True),
        _ts_col("created_at"),
        _ts_col("updated_at"),
    )

    op.create_table(
        "creators",
        ID(),
        sa.Column("platform", sa.String(16), nullable=False),
        sa.Column("platform_uid", sa.String(128), nullable=False),
        sa.Column("nickname", sa.String(128), nullable=True),
        sa.Column("avatar_url", sa.Text(), nullable=True),
        sa.Column("homepage_url", sa.Text(), nullable=True),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.UniqueConstraint("platform", "platform_uid", name="uq_creators_platform_uid"),
    )

    op.create_table(
        "writing_skills",
        ID(),
        sa.Column("name", sa.String(64), nullable=False, unique=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        _ts_col("created_at"),
    )

    op.create_table(
        "metric_dimensions",
        ID(),
        sa.Column("key", sa.String(32), nullable=False, unique=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("unit", sa.String(16), nullable=True),
        sa.Column("caliber", sa.Text(), nullable=True),
        sa.Column("source", sa.String(64), nullable=True),
    )

    op.create_table(
        "visual_skills",
        ID(),
        sa.Column("name", sa.String(64), nullable=False, unique=True),
        sa.Column("config", sa.JSON(), nullable=False),
        _ts_col("created_at"),
        _ts_col("updated_at"),
    )

    op.create_table(
        "asset_files",
        ID(),
        sa.Column("bucket", sa.String(64), nullable=False),
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("content_type", sa.String(64), nullable=True),
        sa.Column("lifecycle", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        _ts_col("created_at"),
        sa.Index("ix_asset_files_lifecycle", "lifecycle", "expires_at"),
    )

    op.create_table(
        "task_runs",
        ID(),
        sa.Column("task_type", sa.String(32), nullable=False),
        sa.Column("target_id", sa.String(64), nullable=False),
        sa.Column("run_key", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_retries", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("task_type", "target_id", "run_key", name="uq_task_runs_idempotency"),
    )

    op.create_table(
        "daily_quotas",
        ID(),
        sa.Column("category", sa.String(16), nullable=False),
        sa.Column("quota_date", sa.Date(), nullable=False),
        sa.Column("used", sa.Integer(), nullable=False),
        sa.Column("quota_limit", sa.Integer(), nullable=False),
        sa.UniqueConstraint("category", "quota_date", name="uq_daily_quotas_category_date"),
    )

    # 2. 依赖 users
    op.create_table(
        "benchmark_accounts",
        ID(),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("creator_id", sa.Integer(), sa.ForeignKey("creators.id"), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("check_interval_minutes", sa.Integer(), nullable=False),
        sa.Column("first_study_limit", sa.Integer(), nullable=False),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        _ts_col("created_at"),
        sa.UniqueConstraint("user_id", "creator_id", name="uq_benchmark_user_creator"),
    )

    op.create_table(
        "audit_logs",
        ID(),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("entity_type", sa.String(32), nullable=True),
        sa.Column("entity_id", sa.String(64), nullable=True),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=True),
        sa.Column("ip", sa.String(64), nullable=True),
        _ts_col("created_at"),
    )

    # 3. 依赖 creators
    op.create_table(
        "source_works",
        ID(),
        sa.Column("creator_id", sa.Integer(), sa.ForeignKey("creators.id"), nullable=False),
        sa.Column("platform", sa.String(16), nullable=False),
        sa.Column("work_id", sa.String(128), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("cover_url", sa.Text(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("author_name", sa.String(128), nullable=True),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("discovered_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("parse_status", sa.String(16), nullable=False),
        sa.Column("parse_error", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.UniqueConstraint("platform", "work_id", name="uq_source_works_platform_work"),
        sa.Index("ix_source_works_creator", "creator_id"),
    )

    # 4. 依赖 source_works
    op.create_table(
        "transcripts",
        ID(),
        sa.Column("work_id", sa.Integer(), sa.ForeignKey("source_works.id"), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("words", sa.JSON(), nullable=True),
        sa.Column("model", sa.String(64), nullable=True),
        sa.Column("language", sa.String(16), nullable=False),
        _ts_col("created_at"),
    )

    op.create_table(
        "material_features",
        ID(),
        sa.Column("work_id", sa.Integer(), sa.ForeignKey("source_works.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("theme", sa.Text(), nullable=True),
        sa.Column("audience", sa.Text(), nullable=True),
        sa.Column("core_viewpoint", sa.Text(), nullable=True),
        sa.Column("hook", sa.Text(), nullable=True),
        sa.Column("structure", sa.Text(), nullable=True),
        sa.Column("emotion", sa.Text(), nullable=True),
        sa.Column("features", sa.JSON(), nullable=True),
        sa.Column("analysis", sa.Text(), nullable=True),
        sa.Column("model", sa.String(64), nullable=True),
        sa.Column("prompt_version", sa.String(64), nullable=True),
        _ts_col("created_at"),
        sa.UniqueConstraint("work_id", "version", name="uq_material_features_work_version"),
    )

    # 5. 依赖 users + source_works
    op.create_table(
        "topics",
        ID(),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("entry", sa.String(16), nullable=False),
        sa.Column("base_topic", sa.Text(), nullable=True),
        sa.Column("source_work_id", sa.Integer(), sa.ForeignKey("source_works.id"), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("viewpoint", sa.Text(), nullable=True),
        sa.Column("audience", sa.Text(), nullable=True),
        sa.Column("angle", sa.Text(), nullable=True),
        sa.Column("reference_sources", sa.JSON(), nullable=True),
        sa.Column("recommendation", sa.Text(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        _ts_col("created_at"),
        _ts_col("updated_at"),
    )

    # 6. 依赖 topics + users
    op.create_table(
        "content_projects",
        ID(),
        sa.Column("topic_id", sa.Integer(), sa.ForeignKey("topics.id"), nullable=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        _ts_col("created_at"),
        _ts_col("updated_at"),
        sa.Index("ix_content_projects_status", "status"),
    )

    # 7. 依赖 knowledge_cards（先建）
    op.create_table(
        "knowledge_cards",
        ID(),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("viewpoint", sa.Text(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("is_locked", sa.Boolean(), nullable=False),
        sa.Column("current_version", sa.Integer(), nullable=False),
        _ts_col("created_at"),
        _ts_col("updated_at"),
    )

    op.create_table(
        "knowledge_card_versions",
        ID(),
        sa.Column("card_id", sa.Integer(), sa.ForeignKey("knowledge_cards.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("diff", sa.JSON(), nullable=True),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("model", sa.String(64), nullable=True),
        sa.Column("prompt_version", sa.String(64), nullable=True),
        _ts_col("created_at"),
        sa.UniqueConstraint("card_id", "version", name="uq_kcard_versions_card_version"),
    )

    op.create_table(
        "knowledge_sources",
        ID(),
        sa.Column("card_id", sa.Integer(), sa.ForeignKey("knowledge_cards.id"), nullable=False),
        sa.Column("work_id", sa.Integer(), sa.ForeignKey("source_works.id"), nullable=False),
        sa.Column("relation", sa.String(16), nullable=False),
        sa.Column("excerpt", sa.Text(), nullable=True),
        _ts_col("created_at"),
    )

    # 8. 依赖 content_projects
    op.create_table(
        "outlines",
        ID(),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("content_projects.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        _ts_col("created_at"),
    )

    op.create_table(
        "scripts",
        ID(),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("content_projects.id"), nullable=False),
        sa.Column("current_version", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        _ts_col("created_at"),
        _ts_col("updated_at"),
    )

    op.create_table(
        "script_versions",
        ID(),
        sa.Column("script_id", sa.Integer(), sa.ForeignKey("scripts.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        _ts_col("created_at"),
        sa.UniqueConstraint("script_id", "version", name="uq_script_versions_script_version"),
    )

    # 9. 依赖 content_projects + asset_files
    op.create_table(
        "video_jobs",
        ID(),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("content_projects.id"), nullable=False),
        sa.Column("job_type", sa.String(24), nullable=False),
        sa.Column("request", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        _ts_col("created_at"),
        _ts_col("updated_at"),
        sa.Index("ix_video_jobs_project", "project_id"),
    )

    op.create_table(
        "video_assets",
        ID(),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("content_projects.id"), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("asset_file_id", sa.Integer(), sa.ForeignKey("asset_files.id"), nullable=False),
        _ts_col("created_at"),
    )

    op.create_table(
        "publications",
        ID(),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("content_projects.id"), nullable=False),
        sa.Column("platform", sa.String(16), nullable=False),
        sa.Column("platform_video_id", sa.String(128), nullable=True),
        sa.Column("publish_url", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        _ts_col("created_at"),
    )

    op.create_table(
        "cost_events",
        ID(),
        sa.Column("category", sa.String(16), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("content_projects.id"), nullable=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("video_jobs.id"), nullable=True),
        sa.Column("vendor", sa.String(64), nullable=True),
        sa.Column("model", sa.String(64), nullable=True),
        sa.Column("units", sa.Numeric(18, 4), nullable=True),
        sa.Column("unit_price", sa.Numeric(18, 6), nullable=True),
        sa.Column("cost", sa.Numeric(18, 6), nullable=True),
        _ts_col("created_at"),
    )

    # 10. 依赖 publications + metric_dimensions + content_projects
    op.create_table(
        "metric_snapshots",
        ID(),
        sa.Column("publication_id", sa.Integer(), sa.ForeignKey("publications.id"), nullable=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("content_projects.id"), nullable=False),
        sa.Column("dimension_id", sa.Integer(), sa.ForeignKey("metric_dimensions.id"), nullable=False),
        sa.Column("value", sa.BigInteger(), nullable=False),
        sa.Column("stat_date", sa.Date(), nullable=False),
        sa.Column("source", sa.String(64), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        _ts_col("created_at"),
        sa.Index("ix_metric_snapshots_project_date", "project_id", "stat_date"),
    )


def downgrade() -> None:
    # 逆拓扑序删除
    for table in [
        "metric_snapshots",
        "cost_events",
        "publications",
        "video_assets",
        "video_jobs",
        "script_versions",
        "scripts",
        "outlines",
        "knowledge_sources",
        "knowledge_card_versions",
        "knowledge_cards",
        "content_projects",
        "topics",
        "material_features",
        "transcripts",
        "source_works",
        "audit_logs",
        "benchmark_accounts",
        "daily_quotas",
        "task_runs",
        "asset_files",
        "visual_skills",
        "metric_dimensions",
        "writing_skills",
        "creators",
        "users",
    ]:
        op.drop_table(table)
