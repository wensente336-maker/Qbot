"""每日配额拦截：限额来自配置，超限返回 429，0 表示不限。

用独立类别名（`*_qa`）避免与流水线测试共用同一配额行。
"""

from httpx import AsyncClient

from app.core.config import settings
from app.services.quota import limit_for, quota_limits


def test_quota_limits_from_config(monkeypatch) -> None:
    monkeypatch.setattr(settings, "quota_limits", '{"render": 3, "llm": 0}')
    assert limit_for("render") == 3
    assert limit_for("llm") == 0
    # 配置里没写的类别走默认值，完全未知的类别不限
    assert limit_for("transcribe") == 30
    assert limit_for("unknown") == 0


def test_quota_limits_invalid_config_falls_back(monkeypatch) -> None:
    monkeypatch.setattr(settings, "quota_limits", "not-a-json")
    assert quota_limits()["render"] == 20


async def test_consume_blocks_when_exceeded(
    client: AsyncClient, auth_headers: dict[str, str], monkeypatch
) -> None:
    monkeypatch.setattr(settings, "quota_limits", '{"render_qa": 2}')

    r = await client.post("/api/v1/quota/render_qa/consume?amount=2", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["used"] == 2
    assert r.json()["quota_limit"] == 2

    r = await client.post("/api/v1/quota/render_qa/consume?amount=1", headers=auth_headers)
    assert r.status_code == 429
    assert "配额已用尽" in r.json()["detail"]

    # 被拒的请求不能把计数继续推高
    r = await client.get("/api/v1/quota/render_qa", headers=auth_headers)
    assert r.json()["used"] == 2


async def test_zero_limit_means_unlimited(
    client: AsyncClient, auth_headers: dict[str, str], monkeypatch
) -> None:
    monkeypatch.setattr(settings, "quota_limits", '{"unlimited_qa": 0}')
    r = await client.post("/api/v1/quota/unlimited_qa/consume?amount=9999", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["used"] == 9999
    assert r.json()["quota_limit"] == 0


async def test_limit_change_takes_effect(
    client: AsyncClient, auth_headers: dict[str, str], monkeypatch
) -> None:
    monkeypatch.setattr(settings, "quota_limits", '{"tts_qa": 5}')
    r = await client.post("/api/v1/quota/tts_qa/consume?amount=4", headers=auth_headers)
    assert r.json()["quota_limit"] == 5

    # 调低限额后，当日配额行同步新值，剩余额度不足以再扣
    monkeypatch.setattr(settings, "quota_limits", '{"tts_qa": 4}')
    r = await client.post("/api/v1/quota/tts_qa/consume?amount=1", headers=auth_headers)
    assert r.status_code == 429

    r = await client.get("/api/v1/quota/tts_qa", headers=auth_headers)
    assert r.json()["quota_limit"] == 4
