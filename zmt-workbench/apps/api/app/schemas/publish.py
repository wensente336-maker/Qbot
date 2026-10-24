"""发布 / 指标 / 成本 / 配额 Pydantic 模型。"""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class PublicationCreate(BaseModel):
    project_id: int
    platform: str = "douyin"
    platform_video_id: str | None = None
    publish_url: str | None = None


class PublicationRead(BaseModel):
    id: int
    project_id: int
    platform: str
    platform_video_id: str | None = None
    publish_url: str | None = None
    published_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MetricSyncRequest(BaseModel):
    publication_id: int
    stat_date: date
    values: dict[str, int] = {}


class MetricDimensionRead(BaseModel):
    id: int
    key: str
    name: str
    unit: str | None = None
    caliber: str | None = None
    source: str | None = None

    model_config = ConfigDict(from_attributes=True)


class MetricSnapshotRead(BaseModel):
    id: int
    publication_id: int | None = None
    project_id: int
    dimension_id: int
    value: int
    stat_date: date
    source: str | None = None

    model_config = ConfigDict(from_attributes=True)


class CostEventCreate(BaseModel):
    category: str  # asr / llm / render / storage / traffic
    project_id: int | None = None
    job_id: int | None = None
    vendor: str | None = None
    model: str | None = None
    units: float | None = None
    unit_price: float | None = None
    cost: float | None = None


class CostEventRead(BaseModel):
    id: int
    category: str
    project_id: int | None = None
    job_id: int | None = None
    vendor: str | None = None
    model: str | None = None
    units: float | None = None
    unit_price: float | None = None
    cost: float | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class QuotaRead(BaseModel):
    category: str
    quota_date: date
    used: int
    quota_limit: int

    model_config = ConfigDict(from_attributes=True)
