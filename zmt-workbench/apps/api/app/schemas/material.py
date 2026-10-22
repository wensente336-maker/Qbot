"""素材与特征 Pydantic 模型。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SourceWorkCreate(BaseModel):
    creator_id: int | None = None
    platform: str = "douyin"
    work_id: str
    title: str | None = None
    cover_url: str | None = None
    source_url: str | None = None
    author_name: str | None = None
    caption: str | None = None


class SourceWorkRead(BaseModel):
    id: int
    creator_id: int | None = None
    platform: str
    work_id: str
    title: str | None = None
    cover_url: str | None = None
    source_url: str | None = None
    author_name: str | None = None
    caption: str | None = None
    published_at: datetime | None = None
    parse_status: str
    discovered_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FeatureExtractRequest(BaseModel):
    work_id: int


class MaterialFeatureRead(BaseModel):
    id: int
    work_id: int
    version: int
    theme: str | None = None
    audience: str | None = None
    core_viewpoint: str | None = None
    hook: str | None = None
    structure: str | None = None
    emotion: str | None = None
    features: list | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
