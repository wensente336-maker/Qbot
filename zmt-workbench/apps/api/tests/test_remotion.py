"""Remotion 接入的纯函数测试：分镜 → props 的时长换算、可用性判定。"""

import asyncio

from app.core import remotion
from app.core.remotion import build_props, render_composition, total_frames


def test_build_props_converts_ms_to_frames() -> None:
    scenes = [
        {"index": 1, "start_ms": 0, "end_ms": 3000, "subtitle": "钩子", "visual": "开场"},
        {"start_ms": 3000, "end_ms": 7500, "subtitle": "论点"},
    ]
    props = build_props(scenes, fps=30)
    assert props["scenes"][0]["durationInFrames"] == 90
    assert props["scenes"][0]["index"] == 1
    assert props["scenes"][1]["durationInFrames"] == 135
    assert props["scenes"][1]["index"] == 2
    assert total_frames(props) == 225


def test_build_props_fills_missing_timing() -> None:
    props = build_props([{"visual": "无时间轴"}], fps=30)
    assert props["scenes"][0]["durationInFrames"] == 90
    assert props["scenes"][0]["subtitle"] == ""


def test_total_frames_has_floor_of_one() -> None:
    assert total_frames({"scenes": []}) == 1


def test_render_composition_is_noop_when_disabled() -> None:
    assert remotion.is_available() is False
    result = asyncio.run(render_composition([{"start_ms": 0, "end_ms": 1000}], "/tmp/never.mp4"))
    assert result is None
