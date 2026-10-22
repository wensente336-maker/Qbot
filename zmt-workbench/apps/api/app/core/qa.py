"""自动质检（4 项）：静音 / 黑屏 / 字幕越界 / 音画不同步。

真实检测由 FFmpeg 在 render 队列执行；此处提供阈值、命令模板与结果汇总结构。
"""

QA_THRESHOLDS = {
    "silence_seconds": 2.0,  # 连续静音 > 2s 告警
    "black_seconds": 1.0,  # 黑屏 > 1s 告警
    "safe_margin_v": 0.15,  # 竖屏安全区：上下各 15%
    "safe_margin_h": 0.08,  # 左右各 8%
    "av_sync_ms": 200,  # 音画偏差 > 200ms 告警
}


def build_silence_detect_cmd(path: str) -> list[str]:
    return [
        "ffmpeg",
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
        "ffmpeg",
        "-i",
        path,
        "-vf",
        f"blackdetect=d={QA_THRESHOLDS['black_seconds']}:pix_th=0.10",
        "-an",
        "-f",
        "null",
        "-",
    ]


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
