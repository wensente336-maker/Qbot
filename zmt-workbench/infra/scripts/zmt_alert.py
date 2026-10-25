#!/usr/bin/env python3
"""飞书群机器人告警发送（仅标准库，无第三方依赖）。

用法：
    zmt_alert.py "文本内容"
    echo "文本内容" | zmt_alert.py

配置（默认读取 /etc/zmt/alerts.env，真实环境变量优先）：
    ALERT_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxxx
    ALERT_KEYWORD=ZMT          # 群机器人若设了自定义关键词，消息必须包含它
未配置 webhook 时只写日志并返回 1，不影响调用方继续执行。
"""

import json
import os
import sys
import time
import urllib.request

LOG_PATH = os.environ.get("ALERT_LOG", "/var/log/zmt-alert.log")
ENV_FILE = os.environ.get("ALERT_ENV", "/etc/zmt/alerts.env")


def load_env() -> None:
    if not os.path.exists(ENV_FILE):
        return
    with open(ENV_FILE, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("'").strip('"'))


def notify(text: str) -> bool:
    load_env()
    keyword = os.environ.get("ALERT_KEYWORD", "ZMT").strip()
    body = f"{keyword} | {text}" if keyword else text
    line = f"[{time.strftime('%F %T')}] {body}"
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass
    print(line)

    url = os.environ.get("ALERT_WEBHOOK_URL", "").strip()
    if not url:
        print("【未外发】ALERT_WEBHOOK_URL 未配置，仅记录日志", file=sys.stderr)
        return False

    payload = json.dumps(
        {"msg_type": "text", "content": {"text": body}}, ensure_ascii=False
    ).encode("utf-8")
    request = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as resp:
            raw = resp.read().decode("utf-8", "replace")
        data = json.loads(raw or "{}")
        # 飞书新版返回 code=0，旧版返回 StatusCode=0
        if data.get("code", data.get("StatusCode", 0)) != 0:
            print(f"告警发送失败：{raw}", file=sys.stderr)
            return False
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"告警发送异常：{exc}", file=sys.stderr)
        return False


if __name__ == "__main__":
    message = " ".join(sys.argv[1:]).strip() or sys.stdin.read().strip()
    if not message:
        print("用法：zmt_alert.py <文本>", file=sys.stderr)
        raise SystemExit(2)
    raise SystemExit(0 if notify(message) else 1)
