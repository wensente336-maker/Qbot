"""ASR / TTS 适配层的纯函数测试（不依赖真实凭据/网络）。"""

from app.core.asr import ASRClient, parse_result_detail, parse_whisper_result
from app.core.tts import split_text


def test_parse_result_detail_expands_word_offsets() -> None:
    detail = [
        {
            "FinalSentence": "你好，今天很开心",
            "StartMs": 0,
            "EndMs": 2000,
            "Words": [
                {"Word": "你好", "OffsetStartMs": 0, "OffsetEndMs": 500},
                {"Word": "今天", "OffsetStartMs": 500, "OffsetEndMs": 1200},
            ],
        },
        {"FinalSentence": "再见", "StartMs": 2000, "EndMs": 2600, "Words": None},
    ]
    text, words = parse_result_detail(detail)
    assert text == "你好，今天很开心再见"
    assert words[0] == {"word": "你好", "start_ms": 0, "end_ms": 500}
    assert words[1] == {"word": "今天", "start_ms": 500, "end_ms": 1200}
    # 无词粒度时退化为整句时间戳
    assert words[2] == {"word": "再见", "start_ms": 2000, "end_ms": 2600}


def test_parse_result_detail_handles_empty() -> None:
    assert parse_result_detail([]) == ("", [])
    assert parse_result_detail(None) == ("", [])  # type: ignore[arg-type]


def test_mock_transcribe_shape() -> None:
    result = ASRClient._mock_transcribe()
    assert result["text"]
    assert len(result["words"]) == 12
    assert set(result["words"][0]) == {"word", "start_ms", "end_ms"}


def test_split_text_keeps_content_and_limit() -> None:
    text = "第一句话。第二句话！第三句话？" * 30
    chunks = split_text(text, limit=140)
    assert len(chunks) > 1
    assert all(len(c) <= 140 for c in chunks)
    assert "".join(chunks) == text


def test_split_text_hard_cuts_long_sentence() -> None:
    text = "无" * 300
    chunks = split_text(text, limit=100)
    assert [len(c) for c in chunks] == [100, 100, 100]


def test_split_text_empty() -> None:
    assert split_text("   ") == []


def test_parse_whisper_result_word_level() -> None:
    data = {
        "text": "你好今天",
        "segments": [
            {
                "text": "你好",
                "start": 0.0,
                "end": 1.2,
                "words": [
                    {"word": "你", "start": 0.0, "end": 0.6},
                    {"word": "好", "start": 0.6, "end": 1.2},
                ],
            },
            {
                "text": "今天",
                "start": 1.2,
                "end": 2.4,
                "words": [{"word": "今天", "start": 1.2, "end": 2.4}],
            },
        ],
    }
    text, words = parse_whisper_result(data)
    assert text == "你好今天"
    assert words[0] == {"word": "你", "start_ms": 0, "end_ms": 600}
    assert words[1] == {"word": "好", "start_ms": 600, "end_ms": 1200}
    assert words[2] == {"word": "今天", "start_ms": 1200, "end_ms": 2400}


def test_parse_whisper_result_segment_fallback() -> None:
    data = {
        "text": "你好今天",
        "segments": [
            {"text": "你好", "start": 0.0, "end": 1.2},
            {"text": "今天", "start": 1.2, "end": 2.4},
        ],
    }
    text, words = parse_whisper_result(data)
    assert text == "你好今天"
    # 无词级时间戳时退化为句级
    assert words[0] == {"word": "你好", "start_ms": 0, "end_ms": 1200}
    assert words[1] == {"word": "今天", "start_ms": 1200, "end_ms": 2400}


def test_parse_whisper_result_empty() -> None:
    assert parse_whisper_result({}) == ("", [])
