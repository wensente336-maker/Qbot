"""ASR 转写客户端（多档优先级，可平滑切换）。

1. `ASR_ENDPOINT`：自定义服务，约定 `POST {audio}` 返回
   `{"text": str, "timestamp": [{"word","start_ms","end_ms"}]}`。
2. `ASR_OPENAI_BASE_URL`：OpenAI 兼容 faster-whisper（如宿主机 meeting-minutes-stt），
   multipart 上传 + `response_format=verbose_json`，优先取词级时间戳、缺失时按句退化。
3. `TENCENT_SECRET_ID/KEY`：腾讯云「录音文件识别」云 API——本地音轨压成 16k 单声道 mp3
   后 base64 直传（SourceType=1，无需 COS），轮询任务结果并展开为词级时间轴。
4. 都未配置：内置 mock 占位词，保证全链路可跑。
"""

import asyncio
import base64
import json
import os
import tempfile

import httpx

from app.core.config import settings
from app.core.render import FFMPEG
from app.core.storage import storage

# 腾讯云「本地音频直传」上限：base64 编码后 ≤ 5MB
TENCENT_MAX_BASE64_BYTES = 5 * 1024 * 1024


class ASRClient:
    @property
    def tencent_enabled(self) -> bool:
        return bool(settings.tencent_secret_id and settings.tencent_secret_key)

    @property
    def openai_enabled(self) -> bool:
        return bool(settings.asr_openai_base_url)

    @property
    def mock_enabled(self) -> bool:
        return not settings.asr_endpoint and not self.openai_enabled and not self.tencent_enabled

    async def transcribe(self, media_ref: str) -> dict:
        """对音视频引用执行转写，返回词级时间轴。"""
        if settings.asr_endpoint:
            return await self._http_transcribe(media_ref)
        if self.openai_enabled:
            return await self._openai_transcribe(media_ref)
        if self.tencent_enabled:
            return await self._tencent_transcribe(media_ref)
        return self._mock_transcribe()

    # ---------- 模式 1：自建 HTTP 服务 ----------
    @staticmethod
    async def _http_transcribe(media_ref: str) -> dict:
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

    # ---------- 模式 2：OpenAI 兼容 faster-whisper ----------
    async def _openai_transcribe(self, media_ref: str) -> dict:
        source = _resolve_local_path(media_ref)
        if not os.path.isfile(source):
            raise ValueError(f"音频文件不存在：{source}")

        audio_path = await _extract_audio(source)
        try:
            return await self._post_openai(audio_path)
        finally:
            if os.path.isfile(audio_path):
                os.remove(audio_path)

    @staticmethod
    async def _post_openai(audio_path: str) -> dict:
        base = settings.asr_openai_base_url.rstrip("/")
        url = f"{base}/audio/transcriptions"
        headers = {}
        if settings.asr_openai_api_key:
            headers["Authorization"] = f"Bearer {settings.asr_openai_api_key}"

        with open(audio_path, "rb") as fh:
            audio_bytes = fh.read()

        model = settings.asr_openai_model or "whisper-1"
        form: list[tuple[str, str]] = [
            ("model", model),
            ("response_format", "verbose_json"),
        ]
        files = {"file": (os.path.basename(audio_path), audio_bytes, "audio/mpeg")}

        async with httpx.AsyncClient(timeout=600) as client:
            # 优先请求词级时间戳；不受支持时丢弃该参数重试
            resp = await client.post(
                url, headers=headers, data=form + [("timestamp_granularities[]", "word")], files=files
            )
            if resp.status_code >= 400:
                resp = await client.post(url, headers=headers, data=form, files=files)
            resp.raise_for_status()
            payload = resp.json()

        text, words = parse_whisper_result(payload)
        return {"text": text, "words": words}

    # ---------- 模式 3：腾讯云录音文件识别 ----------
    async def _tencent_transcribe(self, media_ref: str) -> dict:
        source = _resolve_local_path(media_ref)
        if not os.path.isfile(source):
            raise ValueError(f"音频文件不存在：{source}")

        audio_path = await _extract_audio(source)
        try:
            with open(audio_path, "rb") as fh:
                raw = fh.read()
            encoded = base64.b64encode(raw).decode()
            if len(encoded) > TENCENT_MAX_BASE64_BYTES:
                raise ValueError(
                    f"音频过大（base64 {len(encoded) / 1024 / 1024:.1f}MB > 5MB），"
                    "请裁剪后重试或改用 ASR_ENDPOINT"
                )

            task_id = await asyncio.to_thread(_create_task, encoded, len(raw))
            detail = await _wait_task(task_id)
            text, words = parse_result_detail(detail)
            return {"text": text, "words": words}
        finally:
            if os.path.isfile(audio_path):
                os.remove(audio_path)

    # ---------- 模式 4：mock ----------
    @staticmethod
    def _mock_transcribe() -> dict:
        words = [
            {"word": f"占位词{i}", "start_ms": i * 500, "end_ms": i * 500 + 400} for i in range(12)
        ]
        return {"text": "".join(w["word"] for w in words), "words": words}


def _resolve_local_path(media_ref: str) -> str:
    """把存储 key / 绝对路径解析为本地文件；远程 URL 需先落地。"""
    if media_ref.startswith(("http://", "https://")):
        raise ValueError("腾讯云 ASR 直传模式暂不支持远程 URL，请先本地上传")
    return media_ref if os.path.isabs(media_ref) else storage.local_path(media_ref)


async def _extract_audio(source_path: str, bitrate: str = "32k") -> str:
    """抽取/转码为 16k 单声道 mp3（控制体积以适配本地直传的 5MB 限制）。"""
    if FFMPEG is None:
        raise RuntimeError("未找到 ffmpeg，无法抽取音轨")
    fd, out_path = tempfile.mkstemp(suffix=".mp3", prefix="asr-")
    os.close(fd)
    cmd = [
        FFMPEG,
        "-y",
        "-i",
        source_path,
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-b:a",
        bitrate,
        out_path,
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, err = await asyncio.wait_for(proc.communicate(), timeout=600)
    if proc.returncode != 0:
        if os.path.isfile(out_path):
            os.remove(out_path)
        raise RuntimeError(f"音轨抽取失败：{err.decode('utf-8', 'ignore')[-500:]}")
    return out_path


def _build_client():
    """按需构造腾讯云 ASR 客户端（同步 SDK，调用处用 to_thread 包裹）。"""
    from tencentcloud.asr.v20190614 import asr_client
    from tencentcloud.common import credential
    from tencentcloud.common.profile.client_profile import ClientProfile
    from tencentcloud.common.profile.http_profile import HttpProfile

    cred = credential.Credential(settings.tencent_secret_id, settings.tencent_secret_key)
    http_profile = HttpProfile(endpoint="asr.tencentcloudapi.com")
    client_profile = ClientProfile(httpProfile=http_profile)
    return asr_client.AsrClient(cred, settings.tencent_region, client_profile)


def _create_task(encoded_audio: str, raw_len: int) -> int:
    """提交录音文件识别任务，返回 TaskId。"""
    from tencentcloud.asr.v20190614 import models

    req = models.CreateRecTaskRequest()
    req.EngineModelType = settings.tencent_asr_engine
    req.ChannelNum = 1
    # 3 = 词级时间戳 + 标点 + 按标点分段（字幕场景，基础计费内）
    req.ResTextFormat = 3
    req.SourceType = 1
    req.Data = encoded_audio
    req.DataLen = raw_len
    resp = _build_client().CreateRecTask(req)
    return int(resp.Data.TaskId)


def _query_task(task_id: int) -> dict:
    """查询任务状态，返回 DescribeTaskStatus 响应 dict。"""
    from tencentcloud.asr.v20190614 import models

    req = models.DescribeTaskStatusRequest()
    req.TaskId = task_id
    resp = _build_client().DescribeTaskStatus(req)
    return json.loads(resp.to_json_string())


async def _wait_task(task_id: int, interval: float = 2.0, timeout: float = 600.0) -> list[dict]:
    """轮询直到任务成功，返回 ResultDetail 句子列表。"""
    waited = 0.0
    while waited < timeout:
        data = await asyncio.to_thread(_query_task, task_id)
        status = int((data.get("Data") or {}).get("Status") or 0)
        payload = data.get("Data") or {}
        if status == 2:
            return payload.get("ResultDetail") or []
        if status == 3:
            raise RuntimeError(f"腾讯云 ASR 任务失败：{payload.get('ErrorMsg') or 'unknown'}")
        await asyncio.sleep(interval)
        waited += interval
    raise TimeoutError(f"腾讯云 ASR 任务超时（{timeout:.0f}s，TaskId={task_id}）")


def parse_result_detail(result_detail: list[dict]) -> tuple[str, list[dict]]:
    """把 ResultDetail（句子含词偏移）展开为全局词级时间轴。"""
    texts: list[str] = []
    words: list[dict] = []
    for sentence in result_detail or []:
        final = (sentence.get("FinalSentence") or "").strip()
        if final:
            texts.append(final)
        start = int(sentence.get("StartMs") or 0)
        end = int(sentence.get("EndMs") or start)
        items = sentence.get("Words") or []
        if items:
            for item in items:
                token = (item.get("Word") or "").strip()
                if not token:
                    continue
                word_start = start + int(item.get("OffsetStartMs") or 0)
                word_end = start + int(item.get("OffsetEndMs") or 0)
                words.append(
                    {"word": token, "start_ms": word_start, "end_ms": max(word_end, word_start)}
                )
        elif final:
            # 无词粒度时退化为整句时间戳，保证时间轴不空
            words.append({"word": final, "start_ms": start, "end_ms": max(end, start)})
    return "".join(texts), words


def parse_whisper_result(data: dict) -> tuple[str, list[dict]]:
    """把 OpenAI 兼容 verbose_json 响应展开为词级时间轴（秒 → 毫秒）。

    - segments 内若含 `words`（词级时间戳）则逐词展开；
    - 否则按 segments 的 start/end 退化到「句级」时间轴，保证粗剪可用。
    """
    segments = data.get("segments") or []
    has_words = any((seg.get("words") or []) for seg in segments)

    texts: list[str] = []
    words: list[dict] = []
    for seg in segments:
        text = (seg.get("text") or "").strip()
        if text:
            texts.append(text)
        start = seg.get("start") or 0.0
        end = seg.get("end") or start
        if has_words:
            for token in seg.get("words") or []:
                word = (token.get("word") or "").strip()
                if not word:
                    continue
                words.append(
                    {
                        "word": word,
                        "start_ms": int(round(float(token.get("start", start)) * 1000)),
                        "end_ms": int(round(float(token.get("end", end)) * 1000)),
                    }
                )
        elif text:
            words.append(
                {
                    "word": text,
                    "start_ms": int(round(float(start) * 1000)),
                    "end_ms": int(round(float(end) * 1000)),
                }
            )
    full_text = data.get("text") or "".join(texts)
    return full_text, words


asr = ASRClient()
