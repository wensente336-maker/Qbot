import subprocess
import sys

sys.path.insert(0, "/app")

SRC = "/data/media/user-uploads/4/e2e-source.mp4"
SRT = "/data/media/render-output/4/final-18.srt"

VARIANTS = {
    "plain": None,
    "small": "FontSize=20,Alignment=2,MarginV=20,Outline=2",
    "current": "FontSize=86,Alignment=2,MarginV=288,MarginL=86,MarginR=86,Outline=2",
}

for name, style in VARIANTS.items():
    vf = f"subtitles={SRT}"
    if style:
        vf += f":force_style='{style}'"
    out = f"/tmp/v-{name}.jpg"
    cmd = [
        "ffmpeg", "-y", "-v", "warning", "-i", SRC, "-ss", "3",
        "-frames:v", "1", "-vf", vf, "-update", "1", out,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    print(name, "rc=", proc.returncode, proc.stderr.strip().splitlines()[-1:] or "")
