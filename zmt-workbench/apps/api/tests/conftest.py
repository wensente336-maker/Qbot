"""测试夹具：使用内存 SQLite + StaticPool 运行全量模型与接口。"""

import os

# 必须在 import 任何 app 模块之前覆盖，避免触发默认的 asyncpg 引擎创建
os.environ["DATABASE_URL"] = "sqlite+aiosqlite://"
# 测试必须离线且确定性：清空外部服务凭据，统一走 mock/本地兜底
for _key in (
    "LLM_API_KEY",
    "ASR_ENDPOINT",
    "ASR_OPENAI_BASE_URL",
    "ASR_OPENAI_MODEL",
    "TTS_ENDPOINT",
    "TTS_EDGE_VOICE",
    "TENCENT_SECRET_ID",
    "TENCENT_SECRET_KEY",
    "COS_SECRET_ID",
    "COS_SECRET_KEY",
    "DOUYIN_ACCESS_TOKEN",
):
    os.environ[_key] = ""

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

# 先注册全部 ORM 模型（并避免 `app` 名字被包模块遮蔽）
import app.models  # noqa: F401
from app.db.base import Base
from app.db.session import get_db
from app.main import app

TEST_DB_URL = "sqlite+aiosqlite://"


@pytest.fixture(scope="session")
async def engine():
    engine = create_async_engine(TEST_DB_URL, poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def client(engine) -> AsyncIterator[AsyncClient]:
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        async with SessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
async def auth_headers(client: AsyncClient) -> dict[str, str]:
    """注册并登录一个测试用户，返回带 token 的请求头。"""
    await client.post(
        "/api/v1/auth/register",
        json={"username": "alice", "password": "secret123"},
    )
    r = await client.post(
        "/api/v1/auth/login",
        json={"username": "alice", "password": "secret123"},
    )
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
