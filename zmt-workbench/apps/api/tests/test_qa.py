"""质检与素材特征归一化的纯函数测试（不依赖数据库/网络）。"""

from app.core.qa import check_subtitle_bounds, parse_black, parse_silence, summarize_qa
from app.services.material import _as_text, _normalize_features


def test_parse_silence_with_end() -> None:
    stderr = (
        "[silencedetect @ 0x1] silence_start: 0\n"
        "[silencedetect @ 0x1] silence_end: 2.5 | silence_duration: 2.5\n"
        "[silencedetect @ 0x1] silence_start: 10\n"
        "[silencedetect @ 0x1] silence_end: 12.25 | silence_duration: 2.25\n"
    )
    events = parse_silence(stderr, duration_ms=13000)
    assert events == [
        {"start_ms": 0, "end_ms": 2500, "duration_ms": 2500},
        {"start_ms": 10000, "end_ms": 12250, "duration_ms": 2250},
    ]


def test_parse_silence_trailing_without_end() -> None:
    events = parse_silence("[x] silence_start: 100.5\n", duration_ms=105000)
    assert events == [{"start_ms": 100500, "end_ms": 105000, "duration_ms": 4500}]


def test_parse_black_pairs_events() -> None:
    stderr = "[blackdetect @ 0x1] black_start:0 black_end:1.5 black_duration:1.5\n"
    assert parse_black(stderr) == [{"start_ms": 0, "end_ms": 1500, "duration_ms": 1500}]


def test_check_subtitle_bounds_accepts_short_line() -> None:
    segments = [{"index": 1, "subtitle": "三秒抓住注意力"}]
    assert check_subtitle_bounds(segments, "1080x1920") == []


def test_check_subtitle_bounds_flags_wide_line() -> None:
    segments = [{"index": 2, "subtitle": "这" * 40}]
    issues = check_subtitle_bounds(segments, "1080x1920")
    assert any(item["reason"] == "单行超出左右安全区" for item in issues)


def test_check_subtitle_bounds_flags_too_many_lines() -> None:
    segments = [{"index": 3, "subtitle": "\n".join(["这是一行字幕"] * 13)}]
    issues = check_subtitle_bounds(segments, "1080x1920")
    assert any(item["reason"] == "行数超出上下安全区" for item in issues)


def test_summarize_qa_requires_all_checks() -> None:
    assert summarize_qa()["passed"] is True
    result = summarize_qa(silence_ok=False)
    assert result["passed"] is False
    assert result["checks"]["silence"] is False


def test_normalize_features_from_string() -> None:
    assert _normalize_features("情绪钩子、反转，共鸣") == ["情绪钩子", "反转", "共鸣"]


def test_normalize_features_from_mixed_list() -> None:
    value = ["标签A", {"label": "标签B"}, {"name": ""}, "", "标签A"]
    assert _normalize_features(value) == ["标签A", "标签B"]


def test_normalize_features_empty_inputs() -> None:
    assert _normalize_features(None) is None
    assert _normalize_features("") is None
    assert _normalize_features([]) is None


def test_as_text_coerces_containers() -> None:
    assert _as_text("  标题 ") == "标题"
    assert _as_text(["A", "B"]) == "A、B"
    assert _as_text({"a": 1}) == '{"a": 1}'
    assert _as_text(None) is None
