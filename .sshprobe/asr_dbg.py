import asyncio
import os
import sys

sys.path.insert(0, "/app")

import httpx

from app.core.config import settings
from app.core.storage import storage


async def main() -> None:
    path = storage.local_path("tts/55021ab286cb4c3cac796dc0e02189eb.mp3")
    url = settings.asr_openai_base_url.rstrip("/") + "/audio/transcriptions"
    headers = {"Authorization": f"Bearer {settings.asr_openai_api_key}"}
    with open(path, "rb") as fh:
        payload = fh.read()
    form = {"model": settings.asr_openai_model or "whisper-1", "response_format": "verbose_json"}
    files = {"file": (os.path.basename(path), payload, "audio/mpeg")}
    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.post(url, headers=headers, data=form, files=files)
    print("status:", resp.status_code)
    data = resp.json()
    print("top keys:", list(data.keys()))
    segs = data.get("segments") or []
    print("segments:", len(segs))
    for seg in segs[:8]:
        print(f"  [{seg.get('start')}-{seg.get('end')}] {seg.get('text')!r} words={len(seg.get('words') or [])}")
    print("words in top:", len(data.get("words") or []))


asyncio.run(main())
