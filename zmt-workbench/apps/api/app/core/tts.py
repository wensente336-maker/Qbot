"""TTS 口播合成客户端（占位）。

接入真实 TTS 服务后，`synthesize` 应返回合成音频的可访问引用（URL 或 key）。
未接入时返回 None，由调用方走"上传口播音频"的兜底路径。
"""

from app.core.config import settings


class TTSClient:
    @property
    def enabled(self) -> bool:
        return bool(settings.tts_endpoint)

    async def synthesize(self, text: str) -> str | None:
        """返回合成音频引用；未接入返回 None。"""
        if not self.enabled:
            return None
        # TODO(补充素材/API)：接入 TTS 服务（如 CosyVoice / 火山 TTS），返回音频 URL/key
        raise NotImplementedError("TTS 服务待接入，请提供 TTS_ENDPOINT 与音频化方案")


tts = TTSClient()
