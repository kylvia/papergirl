#!/usr/bin/env python3
"""papergirl · 推送通知（让自动跑完的 episode 能喊到人）。

episode 在无人值守时跑完，结论默认只进日志没人看。本工具把一行消息推到你配置的渠道，
这样"草稿就绪去发布""今天失败了"能真的到你手机/眼前。

配置（.env，留空则只本地打印、不推送，安全降级）：
  NOTIFY_KIND      feishu | serverchan | bark | slack | generic（默认 generic）
  NOTIFY_WEBHOOK   对应渠道的 webhook URL / key

用法：
  python3 tools/notify.py "📮 papergirl 草稿就绪，去发布"
"""
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


def _post(url: str, data: bytes, headers: dict) -> int:
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.status


def send(msg: str) -> int:
    kind = os.environ.get("NOTIFY_KIND", "generic").lower()
    hook = os.environ.get("NOTIFY_WEBHOOK", "").strip()
    if not hook:
        print(f"[notify:off] {msg}", file=sys.stderr)
        return 0
    try:
        if kind == "feishu":
            body = json.dumps({"msg_type": "text", "content": {"text": msg}}).encode()
            _post(hook, body, {"Content-Type": "application/json"})
        elif kind == "serverchan":
            # Server酱：hook 是 SendKey，推到微信
            url = f"https://sctapi.ftqq.com/{hook}.send"
            body = urllib.parse.urlencode({"title": "papergirl", "desp": msg}).encode()
            _post(url, body, {"Content-Type": "application/x-www-form-urlencoded"})
        elif kind == "bark":
            # Bark：hook 是 base，如 https://api.day.app/<key>
            url = hook.rstrip("/") + "/" + urllib.parse.quote(msg)
            with urllib.request.urlopen(url, timeout=15):
                pass
        elif kind == "slack":
            _post(hook, json.dumps({"text": msg}).encode(), {"Content-Type": "application/json"})
        else:  # generic
            _post(hook, json.dumps({"text": msg}).encode(), {"Content-Type": "application/json"})
    except Exception as e:
        print(f"[notify:fail] {e} | msg: {msg}", file=sys.stderr)
        return 1
    print(f"[notify:{kind}] sent", file=sys.stderr)
    return 0


def main() -> int:
    load_dotenv(ROOT / ".env")
    if len(sys.argv) < 2:
        print("usage: notify.py <message>", file=sys.stderr)
        return 2
    return send(" ".join(sys.argv[1:]))


if __name__ == "__main__":
    sys.exit(main())
