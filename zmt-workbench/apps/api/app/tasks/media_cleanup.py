"""媒体生命周期清理：按前缀保留期删除过期文件，并清理失效的 AssetFile 记录。

保留策略（与 core/storage.py 的前缀定义一致）：
- benchmark/      7 天
- user-uploads/   30 天
- render-output/  永久

容器内手动执行：
    python -m app.tasks.media_cleanup            # 预演，只统计不删除
    python -m app.tasks.media_cleanup --apply    # 真正删除

Celery beat 每日 03:15 自动执行（app.tasks.cleanup_media）。
"""

import argparse
import asyncio
import json
import os
import time

from sqlalchemy import select

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.system import AssetFile
from app.models.video import VideoAsset
from app.tasks.celery_app import celery

# 上传中断残留的 *.part 超过该时长即清理
PART_TTL_SECONDS = 24 * 3600


def retention_targets() -> list[tuple[str, int]]:
    """(前缀, 保留天数)；render-output 不在列表内，即永久保留。"""
    return [
        ("benchmark", settings.benchmark_retention_days),
        ("user-uploads", settings.upload_retention_days),
    ]


def collect_expired(
    root: str, targets: list[tuple[str, int]], now: float
) -> list[str]:
    """返回应删除的文件路径（过期文件 + 超 24h 的半成品 .part）。"""
    expired: list[str] = []
    part_cutoff = now - PART_TTL_SECONDS
    for prefix, days in targets:
        base = os.path.join(root, prefix)
        if not os.path.isdir(base):
            continue
        cutoff = now - days * 86400
        for dirpath, _dirnames, filenames in os.walk(base):
            for name in filenames:
                path = os.path.join(dirpath, name)
                if os.path.islink(path):
                    continue
                try:
                    mtime = os.path.getmtime(path)
                except FileNotFoundError:
                    continue
                if name.endswith(".part"):
                    if mtime < part_cutoff:
                        expired.append(path)
                elif mtime < cutoff:
                    expired.append(path)
    return expired


def prune_empty_dirs(root: str, targets: list[tuple[str, int]], apply: bool) -> int:
    """删除清理后留下的空目录（只在前缀目录内部，不越过 root）。"""
    removed = 0
    for prefix, _days in targets:
        base = os.path.join(root, prefix)
        if not os.path.isdir(base):
            continue
        for dirpath, _dirnames, _filenames in os.walk(base, topdown=False):
            if os.path.abspath(dirpath) == os.path.abspath(base):
                continue
            try:
                if not os.listdir(dirpath):
                    removed += 1
                    if apply:
                        os.rmdir(dirpath)
            except OSError:
                continue
    return removed


async def cleanup_media(apply: bool = False) -> dict:
    """扫描并（可选）删除过期媒体，同时清掉指向已删文件的 AssetFile。"""
    root = os.path.abspath(settings.local_media_dir)
    if root == os.path.sep or not os.path.isdir(root):
        return {"apply": apply, "root": root, "skipped": "媒体目录不存在或非法"}

    targets = retention_targets()
    paths = collect_expired(root, targets, time.time())
    freed = 0
    for path in paths:
        try:
            freed += os.path.getsize(path)
        except FileNotFoundError:
            pass
        if apply:
            try:
                os.remove(path)
            except FileNotFoundError:
                pass

    removed_assets = 0
    async with AsyncSessionLocal() as db:
        assets = (await db.scalars(select(AssetFile).where(AssetFile.bucket == "local"))).all()
        # video_assets 有外键引用，被引用的记录不能删（当作已删除会直接违反约束）
        referenced = set((await db.scalars(select(VideoAsset.asset_file_id))).all())
        for asset in assets:
            if asset.id in referenced:
                continue
            if os.path.exists(os.path.join(root, asset.key)):
                continue
            removed_assets += 1
            if apply:
                await db.delete(asset)
        if apply:
            await db.commit()

    pruned = prune_empty_dirs(root, targets, apply)
    return {
        "apply": apply,
        "root": root,
        "expired_files": len(paths),
        "freed_bytes": freed,
        "removed_assets": removed_assets,
        "pruned_dirs": pruned,
        "sample": paths[:5],
    }


@celery.task(name="app.tasks.cleanup_media")
def cleanup_media_task() -> dict:
    return asyncio.run(cleanup_media(apply=True))


def main() -> None:
    parser = argparse.ArgumentParser(description="媒体生命周期清理")
    parser.add_argument("--apply", action="store_true", help="真正删除；默认只预演")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(cleanup_media(apply=args.apply)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
