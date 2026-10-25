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

    # ASR（自定义服务，约定 POST {audio} → {text,timestamp}；优先级最高）
    asr_endpoint: str = ""

    # ASR（OpenAI 兼容的 faster-whisper，如宿主机的 meeting-minutes-stt）
    # 留空则不启用；enable 后走 httpx multipart 上传，response_format=verbose_json
    asr_openai_base_url: str = ""
    asr_openai_model: str = ""
    asr_openai_api_key: str = ""

    # TTS 口播合成（自定义服务，约定 POST {text} → {audio_url|key}；优先级最高）
    tts_endpoint: str = ""
    tts_voice: str = "default"

    # TTS（OpenAI 兼容语音网关，如宿主机 speech-gateway：POST {base}/audio/speech 直出音频字节）
    tts_openai_base_url: str = ""
    tts_openai_api_key: str = ""
    tts_openai_voice: str = ""
    tts_openai_speed: int | None = None

    # TTS（edge-tts 微软 Edge 朗读引擎；voice 非空即启用，优先级高于腾讯云）
    tts_edge_voice: str = ""
    tts_edge_rate: str = "+0%"
    tts_edge_volume: str = "+0%"

    # 腾讯云云 API（ASR 录音文件识别 + TTS 语音合成；两者均留空时降级为 mock/禁用）
    # 注：4C/3.6G 无 GPU 的 CVM 不足以自建 FunASR，生产走云 API
    tencent_secret_id: str = ""
    tencent_secret_key: str = ""
    tencent_region: str = "ap-guangzhou"
    tencent_asr_engine: str = "16k_zh"
    tencent_tts_voice_type: str = "101001"
    tencent_tts_speed: float = 0.0
    tencent_tts_volume: float = 0.0
    tencent_tts_sample_rate: int = 16000

    # Remotion 模板渲染（可选）：需 renderer 依赖 + Chromium，未启用时全部走 FFmpeg
    remotion_enabled: bool = False
    remotion_dir: str = "apps/renderer"
    remotion_entry: str = "src/index.ts"
    remotion_composition: str = "VideoTemplate"
    remotion_timeout_seconds: int = 900
    remotion_browser_executable: str = ""

    # 腾讯云 COS（留空则由 local_media_dir 本地磁盘兜底）
    cos_secret_id: str = ""
    cos_secret_key: str = ""
    cos_bucket: str = "zmt-workbench"
    cos_region: str = "ap-guangzhou"

    # 抖音数据源（P0 授权验证后填充）
    douyin_access_token: str = ""

    # 本地媒体目录（无 COS 时的兜底存储根目录）
    local_media_dir: str = "media"

    # 上传限制：单文件大小上限（MB），流式落盘，超出直接 413
    max_upload_mb: int = 2048

    # CORS：逗号分隔的允许来源。同源部署（前端经 /zmt 反代）无需跨域，留空即关闭；
    # 本地开发默认放行 Next dev server。
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
