"""内容项目与状态机 Pydantic 模型。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# 状态机顺序（只允许逐级向前推进）
PROJECT_STATUSES: list[str] = [
    "topic_confirmed",
    "outline_confirmed",
    "script_finalized",
    "video_uploaded",
    "ai_editing",
    "video_reviewed",
    "published",
    "weekly_reviewed",
]
STATUS_ORDER: dict[str, int] = {s: i for i, s in enumerate(PROJECT_STATUSES)}


class ContentProjectCreate(BaseModel):
    topic_id: int | None = None


class ContentProjectUpdate(BaseModel):
    status: str = Field(description="目标状态，须为当前状态的下一阶段")


class ContentProjectRead(BaseModel):
    id: int
    topic_id: int | None = None
    user_id: int
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
