#!/usr/bin/env python3
"""papergirl · 推送通知（让自动跑完的 episode 能喊到人）。

episode 在无人值守时跑完，结论默认只进日志没人看。本工具把一行消息推到你配置的渠道，
这样"草稿就绪去发布""今天失败了"能真的到你手机/眼前。

配置（.env，留空则只本地打印、不推送，安全降级）：
  NOTIFY_KIND      lark | wecom | feishu | bark | slack | generic（默认 generic）
  NOTIFY_WEBHOOK   对应渠道的 webhook URL / key（lark 时填群 chat_id：oc_xxx）

lark（飞书，shell 出已装好的 lark-cli 发到群，bot 须在该群内）：
  NOTIFY_KIND=lark，NOTIFY_WEBHOOK=<群 chat_id oc_xxx>。

推荐 wecom（企业微信群机器人，腾讯官方，零封号风险、免第三方中继）：
  企业微信建群（自己一人也行）→ 群设置 → 群机器人 → 添加 → 复制 Webhook 地址，
  填进 NOTIFY_WEBHOOK，NOTIFY_KIND=wecom。消息在微信生态里直接收。
  官方文档：https://developer.work.weixin.qq.com/document/path/91770

用法：
  python3 tools/notify.py "📮 papergirl 草稿就绪，去发布"
"""
import json
import os
import shutil
import subprocess
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
        if kind == "lark":
            # 飞书：shell 出 lark-cli 发到群。NOTIFY_WEBHOOK 存 chat_id（oc_xxx）。
            cli = shutil.which("lark-cli")
            if not cli:
                print(f"[notify:fail] lark-cli not on PATH | msg: {msg}", file=sys.stderr)
                return 1
            r = subprocess.run(
                [cli, "im", "+messages-send", "--as", "bot", "--chat-id", hook, "--text", msg],
                capture_output=True, text=True, timeout=30,
            )
            if r.returncode != 0:
                print(f"[notify:fail] lark-cli rc={r.returncode}: {(r.stderr or r.stdout)[:200]}", file=sys.stderr)
                return 1
            print("[notify:lark] sent", file=sys.stderr)
            return 0
        elif kind == "wecom":
            # 企业微信群机器人（官方）：hook 是完整 webhook/send?key=.. 地址
            body = json.dumps({"msgtype": "text", "text": {"content": msg}}).encode()
            _post(hook, body, {"Content-Type": "application/json"})
        elif kind == "feishu":
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
