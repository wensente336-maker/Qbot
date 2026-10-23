"""TTS 口播合成客户端（三档优先级）。

1. `TTS_ENDPOINT`：自建服务，约定 `POST {text}` 返回 `{"audio_url"|"key": str}`。
2. `TENCENT_SECRET_ID/KEY`：腾讯云「语音合成」云 API——按标点分块（单次字符有限），
   逐块合成 mp3 后用 ffmpeg 拼接为一个音频文件，落本地存储并返回 key。
3. 都未配置：返回 None，由调用方走「上传口播音频」的兜底路径。
"""

import asyncio
import base64
import os
import re
import tempfile
import uuid

import httpx

from app.core.config import settings
from app.core.render import FFMPEG
from app.core.storage import storage

# 同步接口单次合成长度有限，按块提交并留出余量
TTS_CHUNK_LIMIT = 140


class TTSClient:
    @property
    def tencent_enabled(self) -> bool:
        return bool(settings.tencent_secret_id and settings.tencent_secret_key)

    @property
    def enabled(self) -> bool:
        return bool(settings.tts_endpoint) or self.tencent_enabled

    async def synthesize(self, text: str) -> str | None:
        """返回合成音频的存储 key；未接入或文本为空时返回 None。"""
        text = (text or "").strip()
        if not text:
            return None
        if settings.tts_endpoint:
            return await self._http_synthesize(text)
        if self.tencent_enabled:
            return await self._tencent_synthesize(text)
        return None

    @staticmethod
    async def _http_synthesize(text: str) -> str:
        async with httpx.AsyncClient(timeout=180) as client:
            resp = await client.post(settings.tts_endpoint, json={"text": text})
            resp.raise_for_status()
            data = resp.json()
        ref = data.get("audio_url") or data.get("key")
        if not ref:
            raise RuntimeError("TTS 服务未返回 audio_url/key")
        return ref

    async def _tencent_synthesize(self, text: str) -> str:
        if FFMPEG is None:
            raise RuntimeError("未找到 ffmpeg，无法拼接合成音频")

        chunks = split_text(text)
        key = f"tts/{uuid.uuid4().hex}.mp3"
        out_path = storage.local_path(key)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)

        if len(chunks) == 1:
            audio = await asyncio.to_thread(_text_to_voice, chunks[0])
            with open(out_path, "wb") as fh:
                fh.write(audio)
            return key

        parts: list[str] = []
        try:
            for chunk in chunks:
                audio = await asyncio.to_thread(_text_to_voice, chunk)
                fd, part = tempfile.mkstemp(suffix=".mp3", prefix="tts-")
                with os.fdopen(fd, "wb") as fh:
                    fh.write(audio)
                parts.append(part)
            await _concat_mp3(parts, out_path)
        finally:
            for part in parts:
                if os.path.isfile(part):
                    os.remove(part)
        return key


def split_text(text: str, limit: int = TTS_CHUNK_LIMIT) -> list[str]:
    """按标点切句并聚合成不超过 limit 的块；超长句强制硬切。"""
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return []
    sentences = re.findall(r"[^。！？!?；;，,、\n]+[。！？!?；;，,、]?", normalized)
    chunks: list[str] = []
    buf = ""
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        while len(sentence) > limit:
            if buf:
                chunks.append(buf)
                buf = ""
            chunks.append(sentence[:limit])
            sentence = sentence[limit:]
        if len(buf) + len(sentence) <= limit:
            buf += sentence
        else:
            chunks.append(buf)
            buf = sentence
    if buf:
        chunks.append(buf)
    return chunks


def _build_client():
    from tencentcloud.common import credential
    from tencentcloud.common.profile.client_profile import ClientProfile
    from tencentcloud.common.profile.http_profile import HttpProfile
    from tencentcloud.tts.v20190823 import tts_client

    cred = credential.Credential(settings.tencent_secret_id, settings.tencent_secret_key)
    http_profile = HttpProfile(endpoint="tts.tencentcloudapi.com")
    client_profile = ClientProfile(httpProfile=http_profile)
    return tts_client.TtsClient(cred, settings.tencent_region, client_profile)


def _text_to_voice(text: str) -> bytes:
    """调用腾讯云同步语音合成，返回 mp3 字节。"""
    from tencentcloud.tts.v20190823 import models

    req = models.TextToVoiceRequest()
    req.Text = text
    req.SessionId = uuid.uuid4().hex
    req.VoiceType = int(settings.tencent_tts_voice_type)
    req.Codec = "mp3"
    req.SampleRate = settings.tencent_tts_sample_rate
    req.Speed = settings.tencent_tts_speed
    req.Volume = settings.tencent_tts_volume
    resp = _build_client().TextToVoice(req)
    if not resp.Audio:
        raise RuntimeError("腾讯云 TTS 未返回音频数据")
    return base64.b64decode(resp.Audio)


async def _concat_mp3(parts: list[str], output_path: str) -> None:
    """用 concat demuxer 无损拼接同参数 mp3 分段。"""
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as fh:
        list_path = fh.name
        for part in parts:
            fh.write(f"file '{os.path.abspath(part)}'\n")
    try:
        cmd = [
            FFMPEG,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            list_path,
            "-c",
            "copy",
            output_path,
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, err = await asyncio.wait_for(proc.communicate(), timeout=300)
        if proc.returncode != 0:
            raise RuntimeError(f"音频拼接失败：{err.decode('utf-8', 'ignore')[-500:]}")
    finally:
        if os.path.isfile(list_path):
            os.remove(list_path)


tts = TTSClient()
