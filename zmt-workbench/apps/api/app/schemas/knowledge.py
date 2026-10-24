"""知识卡片 Pydantic 模型。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class KnowledgeCardGenerate(BaseModel):
    source_work_ids: list[int] = []


class KnowledgeCardRead(BaseModel):
    id: int
    title: str | None = None
    viewpoint: str | None = None
    status: str
    is_locked: bool
    current_version: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class KnowledgeCardLock(BaseModel):
    is_locked: bool


class KnowledgeSourceCreate(BaseModel):
    work_id: int
    relation: str = "support"  # support / supplement / oppose
    excerpt: str | None = None


class KnowledgeSourceRead(BaseModel):
    id: int
    card_id: int
    work_id: int
    relation: str
    excerpt: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
