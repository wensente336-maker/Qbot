"""上传服务：本地磁盘直传（无 COS 兜底）+ COS 预签名直传（占位）。"""

import os

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.storage import storage
from app.models.system import AssetFile

# 分块读写，避免整段读入内存；3.6G 小机器上大文件全量 read 会直接 OOM
CHUNK_SIZE = 1024 * 1024


async def save_upload(
    db: AsyncSession, file: UploadFile, lifecycle: str = "user-uploads", project_id: int = 0
) -> AssetFile:
    """将上传文件流式写入本地磁盘（无 COS 时），并登记 AssetFile。"""
    key = storage.build_key(lifecycle, project_id, file.filename or f"upload-{os.urandom(4).hex()}")
    dest = os.path.join(settings.local_media_dir, key)
    os.makedirs(os.path.dirname(dest), exist_ok=True)

    limit = settings.max_upload_mb * 1024 * 1024
    part = f"{dest}.part"
    size = 0
    try:
        with open(part, "wb") as fh:
            while chunk := await file.read(CHUNK_SIZE):
                size += len(chunk)
                if size > limit:
                    raise HTTPException(
                        status.HTTP_413_CONTENT_TOO_LARGE,
                        f"文件超过 {settings.max_upload_mb} MB 上限",
                    )
                fh.write(chunk)
        if size == 0:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "上传文件为空")
        os.replace(part, dest)
    finally:
        # 中途失败/超限时清掉半成品，避免脏文件堆积
        if os.path.exists(part):
            os.remove(part)

    asset = AssetFile(
        bucket="local",
        key=key,
        url=f"/media/{key}",
        size_bytes=size,
        content_type=file.content_type or "application/octet-stream",
        lifecycle=lifecycle,
        status="uploaded",
    )
    db.add(asset)
    await db.commit()
    await db.refresh(asset)
    return asset


async def presign_upload(
    db: AsyncSession, filename: str, content_type: str, lifecycle: str, project_id: int = 0
) -> tuple[AssetFile, str]:
    """登记待上传文件并返回预签名直传 URL（COS 未接入时回退本地路径）。"""
    key = storage.build_key(lifecycle, project_id, filename)
    asset = AssetFile(
        bucket=settings.cos_bucket if storage.use_cos else "local",
        key=key,
        url=storage.presign_get(key),
        content_type=content_type,
        lifecycle=lifecycle,
        status="pending",
    )
    db.add(asset)
    await db.commit()
    await db.refresh(asset)
    try:
        upload_url = storage.presign_upload(key, content_type)
    except NotImplementedError as exc:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, str(exc)) from exc
    return asset, upload_url
