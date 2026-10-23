"""真实渲染核心：FFmpeg 字幕合成 + 重编码输出。

无 Remotion 时用 FFmpeg 做「缩放/填充 + 字幕烧录 + 音频轨」版本；Remotion 模板为后续
可选扩展（composition 参数预留）。所有命令返回后可交给 render 队列异步执行。
"""

import asyncio
import os
import shutil

FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")


def parse_resolution(resolution: str) -> tuple[int, int]:
    """'1080x1920' → (1080, 1920)。"""
    try:
        w, h = (resolution or "1080x1920").lower().split("x", 1)
        return int(w), int(h)
    except ValueError:
        return 1080, 1920


def _ts(ms: int) -> str:
    """毫秒 → SRT 时间戳 'HH:MM:SS,mmm'。"""
    h, rem = divmod(int(ms), 3600000)
    m, rem = divmod(rem, 60000)
    s, milli = divmod(rem, 1000)
    return f"{h:02}:{m:02}:{s:02},{milli:03}"


def to_srt(segments: list[dict]) -> str:
    """把分镜 [{start_ms, end_ms, subtitle}] 序列化为 SRT 文本。"""
    blocks: list[str] = []
    idx = 1
    for seg in segments:
        text = str(seg.get("subtitle") or seg.get("text") or "").strip()
        if not text:
            continue
        start = int(seg.get("start_ms") or 0)
        end = int(seg.get("end_ms") or (start + 2000))
        if end <= start:
            end = start + 2000
        blocks.append(f"{idx}\n{_ts(start)} --> {_ts(end)}\n{text}\n")
        idx += 1
    return "\n".join(blocks)


def estimated_duration_ms(segments: list[dict]) -> int:
    """由分镜区间推算成片时长（无真实源/ffprobe 时的兜底）。"""
    end = max([int(s.get("end_ms") or 0) for s in segments] + [0])
    return max(end + 500, 2000)


def build_synthetic_cmd(output_path: str, resolution: str, fps: int, duration_ms: int) -> list[str]:
    """无素材源时生成纯色底 + 静音轨的合成片段（保证框架可渲染）。"""
    w, h = parse_resolution(resolution)
    duration = max(1.0, duration_ms / 1000)
    return [
        FFMPEG, "-y",
        "-f", "lavfi", "-i", f"color=c=0x111111:s={w}x{h}:d={duration}:r={fps}",
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k", "-shortest",
        output_path,
    ]


def build_render_cmd(
    input_path: str,
    output_path: str,
    resolution: str,
    fps: int,
    srt_path: str | None,
) -> list[str]:
    """缩放/填充到目标分辨率并（可选）烧录字幕。"""
    w, h = parse_resolution(resolution)
    vf = (
        f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
        f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,fps={fps}"
    )
    if srt_path:
        vf += f",subtitles={srt_path}"
    return [
        FFMPEG, "-y", "-i", input_path,
        "-vf", vf,
        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
        output_path,
    ]


async def render_to_file(
    source_path: str | None,
    output_path: str,
    resolution: str,
    fps: int,
    segments: list[dict],
) -> int:
    """执行真实渲染（字幕烧录 + 重编码）并返回成片时长（毫秒）。

    source_path 为空时先生成合成片段；字幕滤镜不可用（缺 libass/字体）时退回无字幕渲染，
    保证始终能产出成片文件。
    """
    base_dir = os.path.dirname(output_path)
    os.makedirs(base_dir, exist_ok=True)

    srt_path: str | None = None
    srt_text = to_srt(segments)
    if srt_text:
        stem = os.path.splitext(os.path.basename(output_path))[0]
        srt_path = os.path.join(base_dir, f"{stem}.srt")
        with open(srt_path, "w", encoding="utf-8") as fh:
            fh.write(srt_text)

    if source_path and os.path.isfile(source_path):
        base_input = source_path
    else:
        stem = os.path.splitext(os.path.basename(output_path))[0]
        base_path = os.path.join(base_dir, f"{stem}-base.mp4")
        await run_ffmpeg(
            build_synthetic_cmd(base_path, resolution, fps, estimated_duration_ms(segments))
        )
        base_input = base_path

    try:
        await run_ffmpeg(build_render_cmd(base_input, output_path, resolution, fps, srt_path))
    except RuntimeError:
        if not srt_path:
            raise
        await run_ffmpeg(build_render_cmd(base_input, output_path, resolution, fps, None))

    return await probe_duration_ms(output_path) or estimated_duration_ms(segments)


async def run_ffmpeg(cmd: list[str], timeout: int = 1800) -> str:
    """异步执行 FFmpeg，失败时抛带 stderr 摘要的 RuntimeError。"""
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg 失败：{err.decode('utf-8', 'ignore')[-2000:]}")
    return err.decode("utf-8", "ignore")


async def probe_duration_ms(path: str) -> int | None:
    """用 ffprobe 读取成片时长（毫秒）。"""
    if not FFPROBE:
        return None
    proc = await asyncio.create_subprocess_exec(
        FFPROBE, "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", path,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
    )
    out, _ = await asyncio.wait_for(proc.communicate(), timeout=60)
    if proc.returncode != 0:
        return None
    try:
        return int(float(out.decode().strip()) * 1000)
    except ValueError:
        return None
