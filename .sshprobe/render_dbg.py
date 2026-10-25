import asyncio
import sys

sys.path.insert(0, "/app")

from app.core.render import build_render_cmd, run_ffmpeg, subtitle_style


async def main() -> None:
    src = "/data/media/user-uploads/4/e2e-source.mp4"
    out = "/tmp/sub-test.mp4"
    srt = "/data/media/render-output/4/final-18.srt"
    cmd = build_render_cmd(src, out, "1080x1920", 30, srt)
    print("style:", subtitle_style("1080x1920"))
    print("vf:", cmd[cmd.index("-vf") + 1])
    try:
        await run_ffmpeg(cmd)
        print("render ok")
    except RuntimeError as exc:
        print("render failed:", str(exc)[:1500])


asyncio.run(main())
