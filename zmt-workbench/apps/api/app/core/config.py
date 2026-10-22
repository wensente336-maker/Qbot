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

    # LLM（OpenAI 兼容，默认 DeepSeek；留空则走内置 mock）
    llm_base_url: str = "https://api.deepseek.com/v1"
    llm_api_key: str = ""
    llm_model: str = "deepseek-chat"

    # ASR（FunASR 本地服务；留空则走内置 mock）
    asr_endpoint: str = ""

    # TTS 口播合成（占位，接入后填充）
    tts_endpoint: str = ""
    tts_voice: str = "default"

    # 腾讯云 COS（留空则由 local_media_dir 本地磁盘兜底）
    cos_secret_id: str = ""
    cos_secret_key: str = ""
    cos_bucket: str = "zmt-workbench"
    cos_region: str = "ap-guangzhou"

    # 抖音数据源（P0 授权验证后填充）
    douyin_access_token: str = ""

    # 本地媒体目录（无 COS 时的兜底存储根目录）
    local_media_dir: str = "media"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
