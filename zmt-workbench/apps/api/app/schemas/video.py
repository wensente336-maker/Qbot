"""视频链路 Pydantic 模型：上传/转写/粗剪/分镜/渲染/质检。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UploadPresignRequest(BaseModel):
    filename: str
    content_type: str = "video/mp4"
    lifecycle: str = "user-uploads"  # benchmark / user-uploads / render-output


class UploadPresignResponse(BaseModel):
    key: str
    upload_url: str
    asset_file_id: int


class AssetFileRead(BaseModel):
    id: int
    bucket: str
    key: str
    url: str | None = None
    size_bytes: int | None = None
    content_type: str | None = None
    lifecycle: str
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TranscribeRequest(BaseModel):
    asset_ref: str = Field(description="音视频的可访问引用（key / URL / 本地路径）")


class RoughCutRequest(BaseModel):
    cuts: list[tuple[int, int]] = Field(description="删除区间（毫秒），如 [[1200, 3600]]")


class StoryboardRequest(BaseModel):
    script_id: int | None = None


class RenderRequest(BaseModel):
    composition: str = "default"
    resolution: str = "1080x1920"
    fps: int = Field(default=30, ge=1, le=60)


class VideoJobRead(BaseModel):
    id: int
    project_id: int
    job_type: str
    request: dict | None = None
    status: str
    result: dict | None = None
    error: str | None = None
    progress: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
