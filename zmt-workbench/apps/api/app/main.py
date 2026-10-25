"""FastAPI 应用入口。"""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import (
    analytics,
    auth,
    knowledge,
    materials,
    projects,
    publish,
    scripts,
    topics,
    uploads,
    videos,
)
from app.core.config import settings

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["health"])
async def health() -> dict:
    return {"status": "ok"}


app.include_router(auth.router, prefix=settings.api_v1_prefix)
app.include_router(projects.router, prefix=settings.api_v1_prefix)
app.include_router(materials.router, prefix=settings.api_v1_prefix)
app.include_router(knowledge.router, prefix=settings.api_v1_prefix)
app.include_router(topics.router, prefix=settings.api_v1_prefix)
app.include_router(scripts.router, prefix=settings.api_v1_prefix)
app.include_router(uploads.router, prefix=settings.api_v1_prefix)
app.include_router(videos.router, prefix=settings.api_v1_prefix)
app.include_router(publish.router, prefix=settings.api_v1_prefix)
app.include_router(analytics.router, prefix=settings.api_v1_prefix)

# 本地媒体直出：成片 / TTS / 上传件都以 /media/{key} 对外，未接 COS 时由 API 直接托管
os.makedirs(settings.local_media_dir, exist_ok=True)
app.mount("/media", StaticFiles(directory=settings.local_media_dir), name="media")
