"""应用配置（pydantic-settings，从环境变量 / .env 读取）。"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "自媒体 AI 工作台"
    api_v1_prefix: str = "/api/v1"

    # 认证（生产必须通过环境变量覆盖）
    secret_key: str = "dev-only-secret-key-change-me-in-production-code"
    access_token_expire_minutes: int = 60 * 24  # 默认 24 小时

    # 数据访问（async，应用与 Alembic 迁移共用）
    database_url: str = "postgresql+asyncpg://zmt:zmt@localhost:5432/zmt"

    # 队列
    redis_url: str = "redis://localhost:6379/0"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
