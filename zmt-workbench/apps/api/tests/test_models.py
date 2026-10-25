"""验证数据模型完整注册（26 张表）。"""

import app.models  # noqa: F401  # 注册全部模型
from app.db.base import Base


def test_all_26_tables_registered() -> None:
    tables = set(Base.metadata.tables.keys())
    assert len(tables) == 26, f"应注册 26 张表，实际 {len(tables)}：{sorted(tables)}"


def test_key_tables_present() -> None:
    tables = set(Base.metadata.tables.keys())
    expected = {
        "users",
        "creators",
        "benchmark_accounts",
        "source_works",
        "transcripts",
        "material_features",
        "knowledge_cards",
        "knowledge_card_versions",
        "knowledge_sources",
        "topics",
        "content_projects",
        "writing_skills",
        "outlines",
        "scripts",
        "script_versions",
        "video_assets",
        "video_jobs",
        "visual_skills",
        "publications",
        "metric_dimensions",
        "metric_snapshots",
        "asset_files",
        "task_runs",
        "audit_logs",
        "cost_events",
        "daily_quotas",
    }
    assert expected <= tables, f"缺失表：{expected - tables}"
