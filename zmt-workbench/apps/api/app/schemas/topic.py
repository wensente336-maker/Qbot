"""选题 Pydantic 模型。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TopicGenerateRequest(BaseModel):
    entry: str = "theme"  # theme / benchmark
    base_topic: str | None = None
    source_work_id: int | None = None
    count: int = Field(default=10, ge=1, le=20)


class TopicRead(BaseModel):
    id: int
    entry: str
    base_topic: str | None = None
    source_work_id: int | None = None
    title: str | None = None
    viewpoint: str | None = None
    audience: str | None = None
    angle: str | None = None
    recommendation: str | None = None
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
