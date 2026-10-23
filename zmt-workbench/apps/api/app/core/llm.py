"""LLM 客户端（OpenAI 兼容，默认 DeepSeek；无 key 时走内置 mock）。

约定：`mock_enabled` 为 True 时，service 层应直接返回结构化占位结果，
不调用 `complete`（该方法会抛异常提示），从而保证框架在无凭证时可运行。
"""

import json

import httpx

from app.core.config import settings


class LLMClient:
    def __init__(self) -> None:
        self.base_url = settings.llm_base_url.rstrip("/")
        self.api_key = settings.llm_api_key
        self.model = settings.llm_model
        self.last_usage: dict | None = None  # 最近一次调用的 token 用量

    @property
    def mock_enabled(self) -> bool:
        return not self.api_key

    async def complete(self, system: str, user: str, json_mode: bool = False) -> str:
        """调用对话补全，返回文本（json_mode 时为 JSON 字符串）。"""
        if self.mock_enabled:
            raise RuntimeError("LLM mock 模式下不应调用 complete，请在 service 层提前返回占位结果")

        payload: dict = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        async with httpx.AsyncClient(timeout=180) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            resp.raise_for_status()
            data = resp.json()
            self.last_usage = data.get("usage") or None  # 供成本记账读取
            return data["choices"][0]["message"]["content"]

    async def json(self, system: str, user: str) -> dict:
        """调用并解析为 JSON 对象。"""
        raw = await self.complete(system, user, json_mode=True)
        return json.loads(raw)

    async def json_list(self, system: str, user: str) -> list[dict]:
        """调用并解析为 JSON 数组（如选题/分镜等批量生成场景）。"""
        raw = await self.complete(system, user, json_mode=True)
        data = json.loads(raw)
        if isinstance(data, dict):
            # 兼容某些模型返回 {"items": [...]} 的包装
            for v in data.values():
                if isinstance(v, list):
                    return v
            return []
        return data if isinstance(data, list) else []


llm = LLMClient()
