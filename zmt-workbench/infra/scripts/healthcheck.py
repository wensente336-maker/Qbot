#!/usr/bin/env python3
"""ZMT 主机巡检：容器 / 接口 / Redis / 磁盘 / 内存 / 备份新鲜度，异常即飞书告警。

每 10 分钟由 /etc/cron.d/zmt-health 调用；同一问题 6 小时内只告警一次，
恢复后自动清掉状态，下次再出问题立刻恢复告警。

可用环境变量覆盖（便于本地演练）：
    BACKUP_DIR   备份目录，默认 /opt/zmt-workbench/backups/db
    PUBLIC_URL   公网页面地址，默认 https://129.204.35.57/zmt
    HEALTH_STATE 状态文件，默认 /var/lib/zmt/health-state.json
"""

import json
import os
import shutil
import socket
import ssl
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from zmt_alert import notify  # noqa: E402

BACKUP_DIR = os.environ.get("BACKUP_DIR", "/opt/zmt-workbench/backups/db")
PUBLIC_URL = os.environ.get("PUBLIC_URL", "https://129.204.35.57/zmt")
STATE_PATH = Path(os.environ.get("HEALTH_STATE", "/var/lib/zmt/health-state.json"))
API_HEALTH_URL = os.environ.get("API_HEALTH_URL", "http://127.0.0.1:8090/health")

REPEAT_SECONDS = 6 * 3600
BACKUP_MAX_AGE = 26 * 3600
DISK_LIMIT = 85
MEM_AVAILABLE_LIMIT = 8

CONTAINERS = (
    "zmt-api",
    "zmt-web",
    "zmt-postgres",
    "zmt-beat",
    "zmt-worker-monitor",
    "zmt-worker-transcribe",
    "zmt-worker-analyze",
    "zmt-worker-render",
)


def http_status(url: str, insecure: bool = False, timeout: int = 8) -> int:
    context = ssl._create_unverified_context() if insecure else None
    try:
        with urllib.request.urlopen(url, timeout=timeout, context=context) as resp:
            return resp.status
    except Exception as exc:  # noqa: BLE001
        return getattr(exc, "code", 0) or 0


def docker_containers() -> dict[str, str]:
    result = subprocess.run(
        ["docker", "ps", "--format", "{{.Names}}|{{.Status}}"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        return {}
    table: dict[str, str] = {}
    for line in result.stdout.splitlines():
        name, _, status = line.partition("|")
        table[name.strip()] = status.strip()
    return table


def redis_ok() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 6379), timeout=3) as sock:
            sock.sendall(b"PING\r\n")
            return b"PONG" in sock.recv(64)
    except OSError:
        return False


def mem_available_percent() -> float:
    info: dict[str, int] = {}
    with open("/proc/meminfo", encoding="utf-8") as fh:
        for line in fh:
            key, _, rest = line.partition(":")
            info[key.strip()] = int(rest.strip().split()[0])
    total = info.get("MemTotal", 0)
    return (info.get("MemAvailable", 0) / total * 100) if total else 100.0


def latest_backup() -> tuple[Path | None, float, int]:
    """返回 (最新备份文件, 距今秒数, 字节数)。"""
    directory = Path(BACKUP_DIR)
    if not directory.is_dir():
        return None, float("inf"), 0
    files = list(directory.glob("zmt-*.sql.gz"))
    if not files:
        return None, float("inf"), 0
    newest = max(files, key=lambda p: p.stat().st_mtime)
    stat = newest.stat()
    return newest, time.time() - stat.st_mtime, stat.st_size


def collect_problems() -> tuple[list[tuple[str, str]], dict]:
    problems: list[tuple[str, str]] = []
    facts: dict = {}

    containers = docker_containers()
    facts["containers"] = len([c for c in CONTAINERS if c in containers])
    down = [c for c in CONTAINERS if c not in containers]
    if down:
        problems.append(("container-down", f"容器未运行：{', '.join(down)}"))
    unhealthy = [c for c in CONTAINERS if c in containers and "unhealthy" in containers[c]]
    if unhealthy:
        problems.append(("container-unhealthy", f"容器健康检查失败：{', '.join(unhealthy)}"))

    api_code = http_status(API_HEALTH_URL)
    facts["api"] = api_code
    if api_code != 200:
        problems.append(("api-down", f"API /health 返回 {api_code or '无响应'}"))

    site_code = http_status(PUBLIC_URL, insecure=True)
    facts["site"] = site_code
    if site_code != 200:
        problems.append(("site-down", f"公网页面 {PUBLIC_URL} 返回 {site_code or '无响应'}"))

    if not redis_ok():
        problems.append(("redis-down", "Redis 127.0.0.1:6379 无响应"))

    disk = shutil.disk_usage("/")
    disk_pct = disk.used / disk.total * 100
    facts["disk_pct"] = round(disk_pct, 1)
    if disk_pct > DISK_LIMIT:
        problems.append(
            ("disk-full", f"根分区已用 {disk_pct:.1f}%（阈值 {DISK_LIMIT}%），剩余 {disk.free / 2**30:.1f}G")
        )

    mem_pct = mem_available_percent()
    facts["mem_available_pct"] = round(mem_pct, 1)
    if mem_pct < MEM_AVAILABLE_LIMIT:
        problems.append(("mem-low", f"可用内存仅 {mem_pct:.1f}%"))

    newest, age, size = latest_backup()
    facts["backup"] = (
        f"{newest.name}({size / 1024:.0f}KB,{age / 3600:.1f}h)" if newest else "none"
    )
    if newest is None:
        problems.append(("no-backup", f"备份目录 {BACKUP_DIR} 没有找到备份文件"))
    elif age > BACKUP_MAX_AGE:
        problems.append(("stale-backup", f"最近备份已 {age / 3600:.1f} 小时未更新：{newest.name}"))
    elif size < 1024:
        problems.append(("small-backup", f"备份文件过小（{size}B）：{newest.name}"))

    return problems, facts


def load_state() -> dict:
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(state: dict) -> None:
    try:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        STATE_PATH.write_text(json.dumps(state), encoding="utf-8")
    except OSError:
        pass


def main() -> int:
    now = time.time()
    problems, facts = collect_problems()
    summary = " ".join(f"{k}={v}" for k, v in facts.items())
    stamp = time.strftime("%F %T")

    state = load_state()
    active_keys = {key for key, _ in problems}
    # 已恢复：清掉状态，下次异常立即告警
    for key in list(state):
        if key not in active_keys:
            state.pop(key, None)

    if not problems:
        save_state(state)
        print(f"[{stamp}] OK {summary}")
        return 0

    for key, message in problems:
        if now - float(state.get(key, 0)) < REPEAT_SECONDS:
            print(f"[{stamp}] SUPPRESS {key}: {message}")
            continue
        notify(f"主机 {socket.gethostname()} 异常：{message}")
        state[key] = now

    save_state(state)
    print(f"[{stamp}] ALERT {len(problems)} 项 {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
