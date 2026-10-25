"""腾讯云主机端到端链路验证：TTS 造测试片 -> 上传 -> ASR -> 粗剪 -> 口播 -> 渲染 -> 质检"""

import asyncio
import json
import os
import subprocess
import sys
import time

import httpx

sys.path.insert(0, "/app")

API = "http://127.0.0.1:8090/api/v1"
MEDIA = "/data/media"
USERNAME = "qa_demo"
PASSWORD = "QaDemo123!"

NARRATION = (
    "大家好，今天聊一个很多人忽略的问题，为什么你的视频完播率总是上不去。"
    "先说结论，问题往往不在内容质量，而在节奏。第一，开头三秒必须直接给结论，不要做自我介绍，也不要说今天我们来聊聊。"
    "第二，每二十秒制造一次信息增量，让观众有继续看下去的理由，可以是反常识的观点，也可以是一个具体数字。"
    "第三，结尾不要拖泥带水，用一个明确的问题引导评论，比如你卡在哪一步。"
    "第四，画面要跟着信息走，不要一条素材从头放到尾，该切就切。"
    "第五，字幕只保留关键词，不要把整段话都打上去。"
    "这套方法我实测了两周，完播率从百分之十八提到了百分之三十四。"
    "如果你也在做自媒体，记得点赞收藏，我们下期见。"
)


def log(msg: str) -> None:
    print(f"\n=== {msg} ===", flush=True)


def ffprobe(path: str) -> dict:
    out = subprocess.check_output(
        [
            "ffprobe", "-v", "error", "-print_format", "json",
            "-show_format", "-show_streams", path,
        ]
    )
    data = json.loads(out)
    video = next((s for s in data["streams"] if s["codec_type"] == "video"), {})
    audio = next((s for s in data["streams"] if s["codec_type"] == "audio"), {})
    return {
        "duration_s": round(float(data["format"]["duration"]), 2),
        "size_bytes": int(data["format"]["size"]),
        "video": f'{video.get("width")}x{video.get("height")}@{video.get("avg_frame_rate")}',
        "audio": f'{audio.get("codec_name")}/{audio.get("sample_rate")}',
    }


async def call(client: httpx.AsyncClient, method: str, path: str, ok=(200, 201, 204), **kw) -> tuple:
    t0 = time.time()
    resp = await client.request(method, API + path, **kw)
    elapsed = time.time() - t0
    tag = f"{method} {path} -> {resp.status_code} ({elapsed:.1f}s)"
    print(tag, flush=True)
    if resp.status_code not in ok:
        print("  body:", resp.text[:600], flush=True)
        resp.raise_for_status()
    if resp.status_code == 409:
        return None, elapsed
    try:
        return resp.json(), elapsed
    except ValueError:
        return resp.text, elapsed


async def build_test_video() -> tuple[str, float]:
    from app.core.storage import storage
    from app.core.tts import TTSClient

    log("生成旁白音频（豆包 TTS）")
    t0 = time.time()
    key = await TTSClient().synthesize(NARRATION)
    audio_path = storage.local_path(key)
    print(f"narration key={key} size={os.path.getsize(audio_path)} bytes ({time.time() - t0:.1f}s)")

    out_path = os.path.join(MEDIA, "tmp", "e2e-source.mp4")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    log("合成 1080x1920@30 测试视频")
    t0 = time.time()
    subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error",
            "-f", "lavfi", "-i", "testsrc2=size=1080x1920:rate=30",
            "-i", audio_path,
            "-map", "0:v", "-map", "1:a",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-b:v", "2M",
            "-c:a", "aac", "-b:a", "96k", "-shortest", out_path,
        ],
        check=True,
    )
    probe = ffprobe(out_path)
    print(f"source {probe} ({time.time() - t0:.1f}s)")
    return out_path, probe["duration_s"]


async def main() -> None:
    source, duration_s = await build_test_video()

    async with httpx.AsyncClient(timeout=900) as client:
        log("注册 / 登录")
        await call(client, "POST", "/auth/register",
                   json={"username": USERNAME, "password": PASSWORD, "phone": None},
                   ok=(201, 409))
        token, _ = await call(client, "POST", "/auth/login",
                              json={"username": USERNAME, "password": PASSWORD})
        client.headers["Authorization"] = f"Bearer {token['access_token']}"
        await call(client, "GET", "/auth/me")

        project, _ = await call(client, "POST", "/projects", json={"topic_id": None})
        project_id = project["id"]
        print("project_id:", project_id)

        log("上传测试视频")
        with open(source, "rb") as fh:
            asset, upload_s = await call(
                client, "POST", "/uploads",
                files={"file": ("e2e-source.mp4", fh, "video/mp4")},
                data={"lifecycle": "user-uploads", "project_id": str(project_id)},
            )
        asset_ref = asset["key"]
        print(f"asset key={asset_ref} size={asset['size_bytes']} upload={upload_s:.1f}s")

        log("ASR 转写（speech-gateway -> faster-whisper）")
        job, transcribe_s = await call(client, "POST", f"/videos/{project_id}/transcribe",
                                       json={"asset_ref": asset_ref})
        words = (job.get("result") or {}).get("words") or []
        print(f"transcribe={transcribe_s:.1f}s words={len(words)} status={job['status']}")
        print("text:", ((job.get("result") or {}).get("text") or "")[:180])
        if words:
            print("first:", words[0], "... last:", words[-1])

        log("粗剪重映射（删除 1.2s-4.2s）")
        cuts = [[1200, 4200]]
        job, cut_s = await call(client, "POST", f"/videos/{project_id}/rough-cut", json={"cuts": cuts})
        print("merged:", (job.get("result") or {}).get("merged_cuts"), f"({cut_s:.2f}s)")

        log("生成脚本 + TTS 口播")
        try:
            script, gen_s = await call(client, "POST", "/scripts/generate", json={"project_id": project_id})
            print(f"script chars={len(script.get('content') or '')} ({gen_s:.1f}s)")
        except Exception as exc:  # noqa: BLE001
            print("脚本生成失败（LLM 或链路问题）：", exc)
        tts_job, tts_s = await call(client, "POST", f"/videos/{project_id}/tts")
        print(f"tts={tts_s:.1f}s result={json.dumps(tts_job.get('result'), ensure_ascii=False)[:200]}")

        log("分镜 / 逐句字幕（来自 ASR 时间轴）")
        board, board_s = await call(client, "POST", f"/videos/{project_id}/storyboard", json={})
        segments = (board.get("result") or {}).get("segments") or []
        print(f"storyboard={board_s:.1f}s source={(board.get('request') or {}).get('source')} segments={len(segments)}")
        for seg in segments[:3]:
            print("  ", seg)
        if segments:
            print("  末句:", segments[-1])

        log("渲染出片（FFmpeg）")
        render_job, render_s = await call(
            client, "POST", f"/videos/{project_id}/render",
            json={"composition": "default", "resolution": "1080x1920", "fps": 30},
        )
        result = render_job.get("result") or {}
        print(f"render={render_s:.1f}s {json.dumps(result, ensure_ascii=False)[:300]}")
        out_path = os.path.join(MEDIA, result["output_key"])
        srt_path = os.path.splitext(out_path)[0] + ".srt"
        print("voiceover:", result.get("voiceover"), "| srt:", os.path.isfile(srt_path),
              f"({len(open(srt_path, encoding='utf-8').read().splitlines()) if os.path.isfile(srt_path) else 0} 行)")
        if os.path.isfile(out_path):
            print("output probe:", ffprobe(out_path))
        else:
            print("!! 成片文件不存在:", out_path)

        log("质检 QA")
        qa_job, qa_s = await call(client, "POST", f"/videos/jobs/{render_job['id']}/qa")
        print(f"qa={qa_s:.1f}s {json.dumps((qa_job.get('result') or {}).get('qa'), ensure_ascii=False)[:400]}")

        log("任务列表")
        jobs, _ = await call(client, "GET", f"/videos/{project_id}/jobs")
        for j in jobs:
            print(f"  #{j['id']} {j['job_type']:<10} {j['status']:<8} progress={j['progress']}")

    log("耗时汇总")
    print(f"输入时长 {duration_s}s | 转写 {transcribe_s:.1f}s | 渲染 {render_s:.1f}s | TTS {tts_s:.1f}s")


asyncio.run(main())
