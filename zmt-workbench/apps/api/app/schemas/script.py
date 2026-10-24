"""文案（大纲/脚本）Pydantic 模型。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class OutlineGenerate(BaseModel):
    project_id: int


class OutlineApprove(BaseModel):
    approved: bool = True


class OutlineRead(BaseModel):
    id: int
    project_id: int
    version: int
    content: dict
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ScriptGenerate(BaseModel):
    project_id: int
    skill: str = "default"
    intensity: int = Field(default=3, ge=1, le=5)
    length: int = Field(default=500, description="300 / 500 / 800")


class ScriptRead(BaseModel):
    id: int
    project_id: int
    current_version: int
    content: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SegmentRewrite(BaseModel):
    segment: str
    instruction: str


class ScriptVersionRead(BaseModel):
    id: int
    script_id: int
    version: int
    content: str
    note: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
