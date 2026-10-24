"""内容项目状态机测试（S0-5 验收）。"""

from httpx import AsyncClient

FULL_FLOW = [
    "outline_confirmed",
    "script_finalized",
    "video_uploaded",
    "ai_editing",
    "video_reviewed",
    "published",
    "weekly_reviewed",
]


async def test_create_and_advance_full_flow(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    r = await client.post("/api/v1/projects", json={}, headers=auth_headers)
    assert r.status_code == 201, r.text
    project_id = r.json()["id"]
    assert r.json()["status"] == "topic_confirmed"

    for target in FULL_FLOW:
        r = await client.patch(
            f"/api/v1/projects/{project_id}",
            json={"status": target},
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == target


async def test_skip_step_rejected(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    r = await client.post("/api/v1/projects", json={}, headers=auth_headers)
    project_id = r.json()["id"]

    # 从 topic_confirmed 直接跳到 script_finalized（跳过 outline_confirmed）应 422
    r = await client.patch(
        f"/api/v1/projects/{project_id}",
        json={"status": "script_finalized"},
        headers=auth_headers,
    )
    assert r.status_code == 422


async def test_invalid_status_rejected(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    r = await client.post("/api/v1/projects", json={}, headers=auth_headers)
    project_id = r.json()["id"]

    r = await client.patch(
        f"/api/v1/projects/{project_id}",
        json={"status": "not_a_status"},
        headers=auth_headers,
    )
    assert r.status_code == 422


async def test_project_isolation_between_users(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    await client.post("/api/v1/projects", json={}, headers=auth_headers)

    # 第二用户不应看到第一用户的项目
    await client.post(
        "/api/v1/auth/register",
        json={"username": "mallory", "password": "secret123"},
    )
    r = await client.post(
        "/api/v1/auth/login",
        json={"username": "mallory", "password": "secret123"},
    )
    other_headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

    r = await client.get("/api/v1/projects", headers=other_headers)
    assert r.status_code == 200
    assert r.json() == []
