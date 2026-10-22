"""统一导入所有 ORM 模型，确保 Base.metadata 注册完整（Alembic / create_all 依赖）。"""

from app.models.benchmark import (
    BenchmarkAccount,
    Creator,
    MaterialFeature,
    SourceWork,
    Transcript,
)
from app.models.knowledge import KnowledgeCard, KnowledgeCardVersion, KnowledgeSource
from app.models.project import ContentProject
from app.models.publish import MetricDimension, MetricSnapshot, Publication
from app.models.script import Outline, Script, ScriptVersion, WritingSkill
from app.models.system import AssetFile, AuditLog, CostEvent, DailyQuota, TaskRun
from app.models.topic import Topic
from app.models.user import User
from app.models.video import VideoAsset, VideoJob, VisualSkill

__all__ = [
    "User",
    "Creator",
    "BenchmarkAccount",
    "SourceWork",
    "Transcript",
    "MaterialFeature",
    "KnowledgeCard",
    "KnowledgeCardVersion",
    "KnowledgeSource",
    "Topic",
    "ContentProject",
    "WritingSkill",
    "Outline",
    "Script",
    "ScriptVersion",
    "VideoAsset",
    "VideoJob",
    "VisualSkill",
    "Publication",
    "MetricDimension",
    "MetricSnapshot",
    "AssetFile",
    "TaskRun",
    "AuditLog",
    "CostEvent",
    "DailyQuota",
]
