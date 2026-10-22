"""认证闭环测试（S0-4 验收）。"""

from httpx import AsyncClient


async def test_register_login_me(client: AsyncClient) -> None:
    r = await client.post(
        "/api/v1/auth/register",
        json={"username": "alice", "password": "secret123"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["username"] == "alice"

    r = await client.post(
        "/api/v1/auth/login",
        json={"username": "alice", "password": "secret123"},
    )
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    assert token

    r = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    assert r.json()["username"] == "alice"


async def test_wrong_password_rejected(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/auth/register",
        json={"username": "bob", "password": "secret123"},
    )
    r = await client.post(
        "/api/v1/auth/login",
        json={"username": "bob", "password": "wrong-pass"},
    )
    assert r.status_code == 401


async def test_duplicate_username_rejected(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/auth/register",
        json={"username": "carol", "password": "secret123"},
    )
    r = await client.post(
        "/api/v1/auth/register",
        json={"username": "carol", "password": "secret456"},
    )
    assert r.status_code == 409


async def test_protected_requires_token(client: AsyncClient) -> None:
    r = await client.get("/api/v1/auth/me")
    assert r.status_code == 401
