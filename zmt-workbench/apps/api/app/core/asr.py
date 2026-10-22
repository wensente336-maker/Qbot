"""ASR 转写客户端（FunASR Paraformer 词级时间戳；无端点走 mock）。

约定：输出统一为 {"text": str, "words": [{"word","start_ms","end_ms"}]}。
"""

import httpx

from app.core.config import settings


class ASRClient:
    @property
    def mock_enabled(self) -> bool:
        return not settings.asr_endpoint

    async def transcribe(self, media_ref: str) -> dict:
        """对音视频引用执行转写，返回词级时间轴。"""
        if self.mock_enabled:
            return self._mock_transcribe()
        async with httpx.AsyncClient(timeout=360) as client:
            resp = await client.post(settings.asr_endpoint, json={"audio": media_ref})
            resp.raise_for_status()
            data = resp.json()
            return {
                "text": data.get("text", ""),
                "words": [
                    {
                        "word": w.get("word", ""),
                        "start_ms": w.get("start_ms", 0),
                        "end_ms": w.get("end_ms", 0),
                    }
                    for w in data.get("timestamp", [])
                ],
            }

    @staticmethod
    def _mock_transcribe() -> dict:
        words = [
            {"word": f"占位词{i}", "start_ms": i * 500, "end_ms": i * 500 + 400} for i in range(12)
        ]
        return {"text": "".join(w["word"] for w in words), "words": words}


asr = ASRClient()
