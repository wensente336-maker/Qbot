"""Remotion 模板渲染接入（可选）。

启用条件（三者同时满足才会走 Remotion）：
1. `REMOTION_ENABLED=true`
2. renderer 入口文件存在，且 `node_modules` 已安装
3. 系统可执行 `npx` 或 renderer 本地 `remotion` 命令

任一不满足、或渲染失败（超时/非零退出/产物缺失）都返回 `None`，
调用方自动回退到 FFmpeg 渲染，保证主链路不受影响。
"""

import asyncio
import json
import os
import shutil

from app.core.config import settings
from app.core.render import parse_resolution

DEFAULT_SCENE_MS = 3000


def build_props(scenes: list[dict], fps: int = 30) -> dict:
    """把分镜转为 Remotion 组件的 props（时长由毫秒换算为帧数）。"""
    normalized: list[dict] = []
    for i, seg in enumerate(scenes):
        start = int(seg.get("start_ms") or i * DEFAULT_SCENE_MS)
        end = int(seg.get("end_ms") or start + DEFAULT_SCENE_MS)
        if end <= start:
            end = start + DEFAULT_SCENE_MS
        normalized.append(
            {
                "index": int(seg.get("index") or i + 1),
                "visual": str(seg.get("visual") or seg.get("subtitle") or f"SCENE {i + 1}"),
                "subtitle": str(seg.get("subtitle") or ""),
                "accent": str(seg.get("accent") or ""),
                "durationInFrames": max(1, round((end - start) / 1000 * fps)),
            }
        )
    return {"scenes": normalized}


def total_frames(props: dict) -> int:
    frames = sum(int(scene.get("durationInFrames") or 1) for scene in props.get("scenes", []))
    return max(1, frames)


def _cli() -> list[str]:
    local = os.path.join(settings.remotion_dir, "node_modules", ".bin", "remotion")
    if os.path.isfile(local):
        return [local, "render"]
    return ["npx", "remotion", "render"]


def is_available() -> bool:
    """Remotion 是否可用（配置开启 + 依赖就绪 + 命令存在）。"""
    if not settings.remotion_enabled:
        return False
    entry = os.path.join(settings.remotion_dir, settings.remotion_entry)
    has_cli = os.path.isfile(
        os.path.join(settings.remotion_dir, "node_modules", ".bin", "remotion")
    ) or shutil.which("npx") is not None
    return os.path.isfile(entry) and os.path.isdir(
        os.path.join(settings.remotion_dir, "node_modules")
    ) and has_cli


async def render_composition(
    scenes: list[dict],
    output_path: str,
    resolution: str = "1080x1920",
    fps: int = 30,
) -> int | None:
    """调用 Remotion CLI 出片；成功返回时长（毫秒），失败返回 None。"""
    if not scenes or not is_available():
        return None

    width, height = parse_resolution(resolution)
    props = build_props(scenes, fps)
    frames = total_frames(props)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    props_path = f"{output_path}.props.json"
    with open(props_path, "w", encoding="utf-8") as fh:
        json.dump(props, fh, ensure_ascii=False)

    cmd = [
        *_cli(),
        settings.remotion_entry,
        settings.remotion_composition,
        output_path,
        f"--props={props_path}",
        f"--width={width}",
        f"--height={height}",
        f"--fps={fps}",
        "--codec=h264",
    ]
    if settings.remotion_browser_executable:
        cmd.append(f"--browser-executable={settings.remotion_browser_executable}")

    proc = None
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=settings.remotion_dir,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        await asyncio.wait_for(
            proc.communicate(), timeout=settings.remotion_timeout_seconds
        )
    except (TimeoutError, OSError):
        if proc is not None and proc.returncode is None:
            proc.kill()
        return None
    finally:
        if os.path.exists(props_path):
            os.remove(props_path)

    if proc is None or proc.returncode != 0 or not os.path.isfile(output_path):
        return None
    return round(frames / fps * 1000)


async def mux_audio(video_path: str, audio_path: str) -> bool:
    """把口播音轨混入 Remotion 成片（视频流直拷，音频转 AAC）。"""
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        return False

    tmp_path = f"{video_path}.mux.mp4"
    cmd = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-i",
        video_path,
        "-i",
        audio_path,
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-shortest",
        "-movflags",
        "+faststart",
        tmp_path,
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    await proc.communicate()
    if proc.returncode != 0 or not os.path.isfile(tmp_path):
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        return False
    os.replace(tmp_path, video_path)
    return True
