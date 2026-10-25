"""媒体生命周期清理的纯函数测试（只测文件扫描/剪枝，不依赖数据库）。"""

import os
import time

from app.tasks.media_cleanup import collect_expired, prune_empty_dirs

TARGETS = [("benchmark", 7), ("user-uploads", 30)]


def _touch(path: str, age_days: float) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(b"x")
    ts = time.time() - age_days * 86400
    os.utime(path, (ts, ts))


def test_collect_expired_respects_per_prefix_retention(tmp_path) -> None:
    root = str(tmp_path)
    _touch(os.path.join(root, "benchmark/1/old.mp4"), 10)
    _touch(os.path.join(root, "benchmark/1/new.mp4"), 1)
    _touch(os.path.join(root, "user-uploads/0/keep.mp4"), 10)
    _touch(os.path.join(root, "user-uploads/0/drop.mp4"), 40)
    _touch(os.path.join(root, "render-output/0/final-1.mp4"), 400)
    _touch(os.path.join(root, "user-uploads/0/stale.mp4.part"), 2)
    _touch(os.path.join(root, "user-uploads/0/live.mp4.part"), 0.01)

    expired = collect_expired(root, TARGETS, time.time())
    names = sorted(os.path.basename(p) for p in expired)
    # render-output 永久保留；未超 24h 的 .part 不动
    assert names == ["drop.mp4", "old.mp4", "stale.mp4.part"]


def test_prune_empty_dirs_only_inside_prefix(tmp_path) -> None:
    root = str(tmp_path)
    _touch(os.path.join(root, "benchmark/9/old.mp4"), 10)
    for path in collect_expired(root, TARGETS, time.time()):
        os.remove(path)

    removed = prune_empty_dirs(root, TARGETS, apply=True)
    assert removed == 1
    assert not os.path.exists(os.path.join(root, "benchmark/9"))
    # 前缀根目录本身必须保留
    assert os.path.isdir(os.path.join(root, "benchmark"))
