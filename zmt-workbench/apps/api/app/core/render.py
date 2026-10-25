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


def _ass_ts(ms: int) -> str:
    """毫秒 → ASS 时间戳 'H:MM:SS.cc'（百分秒）。"""
    cs = int(round(int(ms) / 10))
    h, rem = divmod(cs, 360000)
    m, rem = divmod(rem, 6000)
    s, centi = divmod(rem, 100)
    return f"{h:d}:{m:02d}:{s:02d}.{centi:02d}"


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


def to_ass(segments: list[dict], resolution: str = "1080x1920") -> str:
    """把分镜序列化为 ASS，画布尺寸即视频像素（字号/边距直接用像素）。

    不能靠 SRT + force_style 定字号：SRT 转 ASS 后画布默认 384x288，
    MarginV=288 会把字幕顶出画面（烧录看似成功但成片无字）。
    """
    w, h = parse_resolution(resolution)
    font_size = max(16, round(h * 0.045))
    margin_v = round(h * 0.15)
    margin_h = round(w * 0.08)
    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        f"PlayResX: {w}\n"
        f"PlayResY: {h}\n"
        "WrapStyle: 2\n"
        "ScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Default,Noto Sans CJK SC,{font_size},&H00FFFFFF,&H000000FF,&H00000000,"
        f"&H80000000,-1,0,0,0,100,100,0,0,1,2,1,2,{margin_h},{margin_h},{margin_v},1\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    lines = [header]
    for seg in segments:
        text = str(seg.get("subtitle") or seg.get("text") or "").strip()
        if not text:
            continue
        start = int(seg.get("start_ms") or 0)
        end = int(seg.get("end_ms") or (start + 2000))
        if end <= start:
            end = start + 2000
        lines.append(
            "Dialogue: 0,{},{},Default,,0,0,0,,{}".format(
                _ass_ts(start), _ass_ts(end), text.replace("\n", "\\N")
            )
        )
    return "\n".join(lines) + "\n"


def build_render_cmd(
    input_path: str,
    output_path: str,
    resolution: str,
    fps: int,
    subtitle_path: str | None,
) -> list[str]:
    """缩放/填充到目标分辨率并（可选）烧录字幕。"""
    w, h = parse_resolution(resolution)
    vf = (
        f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
        f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,fps={fps}"
    )
    if subtitle_path:
        vf += f",ass={subtitle_path}"
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
    保证始终能产出成片文件。SRT 仍单独落盘，供下载/剪辑软件复用。
    """
    base_dir = os.path.dirname(output_path)
    os.makedirs(base_dir, exist_ok=True)

    subtitle_path: str | None = None
    srt_text = to_srt(segments)
    if srt_text:
        stem = os.path.splitext(os.path.basename(output_path))[0]
        with open(os.path.join(base_dir, f"{stem}.srt"), "w", encoding="utf-8") as fh:
            fh.write(srt_text)
        subtitle_path = os.path.join(base_dir, f"{stem}.ass")
        with open(subtitle_path, "w", encoding="utf-8") as fh:
            fh.write(to_ass(segments, resolution))

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
        await run_ffmpeg(build_render_cmd(base_input, output_path, resolution, fps, subtitle_path))
    except RuntimeError:
        if not subtitle_path:
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
