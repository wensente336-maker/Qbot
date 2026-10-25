"""端到端工作流冒烟测试（S2–S4）：素材→知识→选题→文案→发布→指标→视频。"""

import time

from httpx import AsyncClient

from app.core.timeline import build_remap, merge_cuts, remap


def test_timeline_remap_core_algorithm() -> None:
    cuts = [(1000, 2000)]
    assert merge_cuts(cuts) == [(1000, 2000)]

    table = build_remap([(1000, 2000)])
    assert remap(500, table) == 500
    assert remap(1500, table) == 500
    assert remap(2500, table) == 1500


async def test_full_content_pipeline(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    # 选题
    r = await client.post(
        "/api/v1/topics/generate",
        json={"entry": "theme", "base_topic": "测试主题", "count": 3},
        headers=auth_headers,
    )
    assert r.status_code == 201, r.text
    assert len(r.json()) == 3

    # 素材录入 + 特征提取
    work_id = f"wf_{int(time.time() * 1000)}"
    r = await client.post(
        "/api/v1/materials",
        json={"platform": "douyin", "work_id": work_id, "title": "测试素材"},
        headers=auth_headers,
    )
    assert r.status_code == 201, r.text
    mid = r.json()["id"]

    r = await client.post(
        "/api/v1/materials/feature-extract",
        json={"work_id": mid},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["version"] == 1

    # 知识卡片
    r = await client.post("/api/v1/knowledge/cards", json={}, headers=auth_headers)
    assert r.status_code == 201, r.text

    # 项目 → 大纲 → 文案
    r = await client.post("/api/v1/projects", json={}, headers=auth_headers)
    assert r.status_code == 201, r.text
    pid = r.json()["id"]

    r = await client.post(
        "/api/v1/outlines/generate", json={"project_id": pid}, headers=auth_headers
    )
    assert r.status_code == 201, r.text

    r = await client.post(
        f"/api/v1/outlines/{pid}/approve",
        json={"approved": True},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "approved"

    r = await client.post(
        "/api/v1/scripts/generate",
        json={"project_id": pid, "length": 500},
        headers=auth_headers,
    )
    assert r.status_code == 201, r.text
    assert r.json()["current_version"] == 1

    # 发布 + 指标 + 驾驶舱
    r = await client.post(
        "/api/v1/publications",
        json={"project_id": pid, "platform": "douyin"},
        headers=auth_headers,
    )
    assert r.status_code == 201, r.text
    pub_id = r.json()["id"]

    r = await client.post(
        "/api/v1/metrics/sync",
        json={
            "publication_id": pub_id,
            "stat_date": "2026-10-22",
            "values": {"views": 100, "likes": 10},
        },
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text

    r = await client.get("/api/v1/dashboard", headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json()["project_count"] >= 1

    r = await client.get("/api/v1/weekly-report", headers=auth_headers)
    assert r.status_code == 200, r.text


async def test_video_pipeline(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    r = await client.post("/api/v1/projects", json={}, headers=auth_headers)
    pid = r.json()["id"]

    r = await client.post(
        f"/api/v1/videos/{pid}/transcribe",
        json={"asset_ref": "test.mp4"},
        headers=auth_headers,
    )
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "succeeded"

    r = await client.post(
        f"/api/v1/videos/{pid}/rough-cut",
        json={"cuts": [[100, 200]]},
        headers=auth_headers,
    )
    assert r.status_code == 201, r.text
    assert "remap_table" in r.json()["result"]

    r = await client.post(
        f"/api/v1/videos/{pid}/storyboard", json={}, headers=auth_headers
    )
    assert r.status_code == 201, r.text

    r = await client.post(
        f"/api/v1/videos/{pid}/render",
        json={"composition": "default", "resolution": "1080x1920", "fps": 30},
        headers=auth_headers,
    )
    assert r.status_code == 201, r.text
    job_id = r.json()["id"]

    r = await client.post(f"/api/v1/videos/jobs/{job_id}/qa", headers=auth_headers)
    assert r.status_code == 200, r.text
    qa = r.json()["result"]["qa"]
    # 4 项真实检测均已执行（合成片为静音+黑底，故只校验结构与检测明细，不假设全通过）
    assert set(qa["checks"]) == {"silence", "black", "subtitle", "av_sync"}
    assert "details" in qa


async def test_upload_streaming_and_size_limit(
    client: AsyncClient,
    auth_headers: dict[str, str],
    monkeypatch,
    tmp_path,
) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "local_media_dir", str(tmp_path))
    monkeypatch.setattr(settings, "max_upload_mb", 1)

    r = await client.post(
        "/api/v1/uploads",
        files={"file": ("ok.mp4", b"x" * 2048, "video/mp4")},
        data={"lifecycle": "user-uploads", "project_id": "0"},
        headers=auth_headers,
    )
    assert r.status_code == 201, r.text
    assert r.json()["size_bytes"] == 2048
    assert (tmp_path / r.json()["key"]).is_file()

    r = await client.post(
        "/api/v1/uploads",
        files={"file": ("big.mp4", b"x" * (1024 * 1024 + 1), "video/mp4")},
        data={"lifecycle": "user-uploads", "project_id": "0"},
        headers=auth_headers,
    )
    assert r.status_code == 413, r.text
    # 超限的半成品不能留在磁盘上
    assert not list(tmp_path.rglob("*.part"))
