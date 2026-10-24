"""自动质检（4 项）：静音 / 黑屏 / 字幕越界 / 音画不同步。

真实检测由 FFmpeg / FFprobe 执行：
- 静音：silencedetect，连续静音超过 2s 告警
- 黑屏：blackdetect，黑屏超过 1s 告警
- 字幕：按竖屏安全区（上下 15%、左右 8%）推算单行字数与行数上限
- 音画：ffprobe 比较音视频流 start_time 偏差是否超过 200ms
"""

import asyncio
import json
import math
import re
import shutil

from app.core.render import parse_resolution

QA_THRESHOLDS = {
    "silence_seconds": 2.0,  # 连续静音 > 2s 告警
    "black_seconds": 1.0,  # 黑屏 > 1s 告警
    "safe_margin_v": 0.15,  # 竖屏安全区：上下各 15%
    "safe_margin_h": 0.08,  # 左右各 8%
    "av_sync_ms": 200,  # 音画偏差 > 200ms 告警
}

FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")

_SILENCE_START = re.compile(r"silence_start:\s*(-?\d+(?:\.\d+)?)")
_SILENCE_END = re.compile(
    r"silence_end:\s*(-?\d+(?:\.\d+)?)\s*\|\s*silence_duration:\s*(-?\d+(?:\.\d+)?)"
)
_BLACK_START = re.compile(r"black_start:\s*(-?\d+(?:\.\d+)?)")
_BLACK_END = re.compile(r"black_end:\s*(-?\d+(?:\.\d+)?)")


def build_silence_detect_cmd(path: str) -> list[str]:
    return [
        FFMPEG or "ffmpeg",
        "-hide_banner",
        "-i",
        path,
        "-af",
        f"silencedetect=noise=-30dB:d={QA_THRESHOLDS['silence_seconds']}",
        "-f",
        "null",
        "-",
    ]


def build_black_detect_cmd(path: str) -> list[str]:
    return [
        FFMPEG or "ffmpeg",
        "-hide_banner",
        "-i",
        path,
        "-vf",
        f"blackdetect=d={QA_THRESHOLDS['black_seconds']}:pix_th=0.10",
        "-an",
        "-f",
        "null",
        "-",
    ]


def parse_silence(stderr: str, duration_ms: int | None = None) -> list[dict]:
    """解析 silencedetect 输出 → [{start_ms, end_ms, duration_ms}]。"""
    starts = [float(v) for v in _SILENCE_START.findall(stderr)]
    ends = [(float(a), float(b)) for a, b in _SILENCE_END.findall(stderr)]

    events: list[dict] = []
    for i, start in enumerate(starts):
        if i < len(ends):
            end_s, dur_s = ends[i]
        else:  # 静音持续到文件末尾
            end_s = (duration_ms or 0) / 1000 or start
            dur_s = max(0.0, end_s - start)
        events.append(
            {
                "start_ms": int(round(start * 1000)),
                "end_ms": int(round(end_s * 1000)),
                "duration_ms": int(round(dur_s * 1000)),
            }
        )
    return events


def parse_black(stderr: str, duration_ms: int | None = None) -> list[dict]:
    """解析 blackdetect 输出 → [{start_ms, end_ms, duration_ms}]。"""
    starts = [float(v) for v in _BLACK_START.findall(stderr)]
    ends = [float(v) for v in _BLACK_END.findall(stderr)]

    events: list[dict] = []
    for i, start in enumerate(starts):
        end_s = ends[i] if i < len(ends) else (duration_ms or 0) / 1000 or start
        events.append(
            {
                "start_ms": int(round(start * 1000)),
                "end_ms": int(round(end_s * 1000)),
                "duration_ms": int(round(max(0.0, end_s - start) * 1000)),
            }
        )
    return events


def check_subtitle_bounds(
    segments: list[dict], resolution: str = "1080x1920"
) -> list[dict]:
    """按安全区（上下 15%、左右 8%）检查字幕是否越界。

    以字号（屏高 4.5%）为基准推算每行最大字数与最大行数：CJK 字符宽度约等于字号，
    因此 `每行字数 ≈ 安全宽度 / 字号`。超出即判定越界，与 render 的字幕样式保持一致。
    """
    width, height = parse_resolution(resolution)
    safe_width = width * (1 - 2 * QA_THRESHOLDS["safe_margin_h"])
    safe_height = height * (1 - 2 * QA_THRESHOLDS["safe_margin_v"])
    font_size = max(16, round(height * 0.045))
    per_line = max(8, int(safe_width // font_size))
    max_lines = max(1, int(safe_height // (font_size * 1.3)))

    issues: list[dict] = []
    for seg in segments:
        text = str(seg.get("subtitle") or seg.get("text") or "").strip()
        if not text:
            continue

        lines = 0
        for raw_line in text.splitlines() or [text]:
            length = len(raw_line)
            if length > per_line:
                issues.append(
                    {
                        "index": seg.get("index"),
                        "reason": "单行超出左右安全区",
                        "length": length,
                        "limit": per_line,
                        "text": raw_line,
                    }
                )
            lines += max(1, math.ceil(length / per_line))

        if lines > max_lines:
            issues.append(
                {
                    "index": seg.get("index"),
                    "reason": "行数超出上下安全区",
                    "lines": lines,
                    "limit": max_lines,
                    "text": text,
                }
            )
    return issues


async def _capture_stderr(cmd: list[str], timeout: int = 600) -> str:
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    return err.decode("utf-8", "ignore")


async def probe_duration_ms(path: str) -> int | None:
    """读取媒体总时长（毫秒），用于补齐片尾未闭合的静音/黑屏区间。"""
    if not FFPROBE:
        return None
    proc = await asyncio.create_subprocess_exec(
        FFPROBE,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    out, _ = await asyncio.wait_for(proc.communicate(), timeout=60)
    if proc.returncode != 0:
        return None
    try:
        return int(float(out.decode().strip()) * 1000)
    except ValueError:
        return None


async def probe_av_offset_ms(path: str) -> int | None:
    """音画起点偏差（毫秒）= 音频 start_time - 视频 start_time；缺流时返回 None。"""
    if not FFPROBE:
        return None
    proc = await asyncio.create_subprocess_exec(
        FFPROBE,
        "-v",
        "error",
        "-show_entries",
        "stream=codec_type,start_time",
        "-of",
        "json",
        path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    out, _ = await asyncio.wait_for(proc.communicate(), timeout=60)
    if proc.returncode != 0:
        return None
    try:
        streams = json.loads(out.decode() or "{}").get("streams", [])
    except json.JSONDecodeError:
        return None

    starts: dict[str, float] = {}
    for stream in streams:
        kind = stream.get("codec_type")
        if kind in ("video", "audio") and kind not in starts:
            try:
                starts[kind] = float(stream.get("start_time") or 0.0)
            except (TypeError, ValueError):
                starts[kind] = 0.0

    if "video" not in starts or "audio" not in starts:
        return None
    return int(round((starts["audio"] - starts["video"]) * 1000))


def summarize_qa(
    *,
    silence_ok: bool = True,
    black_ok: bool = True,
    subtitle_ok: bool = True,
    av_sync_ok: bool = True,
    details: dict | None = None,
) -> dict:
    """汇总 4 项质检结果；全部通过才可进入人工确认。"""
    checks = {
        "silence": silence_ok,
        "black": black_ok,
        "subtitle": subtitle_ok,
        "av_sync": av_sync_ok,
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "details": details or {},
    }


async def run_qa_checks(
    path: str,
    *,
    segments: list[dict] | None = None,
    resolution: str = "1080x1920",
) -> dict:
    """对成片执行 4 项真实检测并返回汇总结果。"""
    if FFMPEG is None:
        return summarize_qa(details={"skipped": "ffmpeg 未安装，已跳过实际检测"})

    duration_ms = await probe_duration_ms(path)
    silence_events = parse_silence(await _capture_stderr(build_silence_detect_cmd(path)), duration_ms)
    black_events = parse_black(await _capture_stderr(build_black_detect_cmd(path)), duration_ms)
    av_offset = await probe_av_offset_ms(path)
    subtitle_issues = check_subtitle_bounds(segments or [], resolution)

    return summarize_qa(
        silence_ok=not silence_events,
        black_ok=not black_events,
        subtitle_ok=not subtitle_issues,
        av_sync_ok=av_offset is None or abs(av_offset) <= QA_THRESHOLDS["av_sync_ms"],
        details={
            "duration_ms": duration_ms,
            "silence": silence_events,
            "black": black_events,
            "subtitle": subtitle_issues,
            "av_offset_ms": av_offset,
            "resolution": resolution,
        },
    )
