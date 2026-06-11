#!/usr/bin/env python3
"""papergirl · 提取 X 登录 cookie 给 last30days 用（auth_token + ct0）。

前置：browser-relay 在跑、Chrome 装了它的扩展、有一个已登录的 X 标签页，
并且已对本地 relay 打过 ops/patch-browser-relay.mjs（加 /api/cookies 路由）。

做什么：通过 relay 的 /api/cookies（走 CDP Network.getAllCookies，能读 httpOnly）
取 .x.com / .twitter.com 的 cookie，提取 auth_token + ct0，写进 gitignored 的
state/x-cookies.env（0600）。episode-runner.sh 会 source 它，把 AUTH_TOKEN/CT0
传给 last30days。

安全：auth_token 是密码级凭证。本脚本只把它写进 0600 文件，绝不打印其值
（成功时只回显存在性 + 长度 + 掩码）。

用法：
  python3 tools/x_cookies.py            # 提取并写入 state/x-cookies.env
  python3 tools/x_cookies.py --check    # 只检查能否提取，不写文件
"""
import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RELAY = os.environ.get("BROWSER_RELAY_URL", "http://127.0.0.1:18795")
OUT = ROOT / "state" / "x-cookies.env"
X_HOSTS = ("x.com", "twitter.com")
WANT = ("auth_token", "ct0")


def _get(path: str):
    with urllib.request.urlopen(f"{RELAY}{path}", timeout=10) as r:
        return json.loads(r.read())


def _post(path: str, body: dict):
    req = urllib.request.Request(
        f"{RELAY}{path}", method="POST",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def find_x_tab() -> str:
    try:
        data = _get("/api/tabs")
    except Exception as e:
        sys.exit(f"error: relay 不可达（{RELAY}）：{e}\n先确认 browser-relay 在跑：browser-relay status")
    tabs = data.get("tabs") if isinstance(data, dict) else data
    for t in tabs or []:
        url = (t.get("url") or "")
        if any(h in url for h in X_HOSTS):
            return t.get("id") or t.get("tabId") or ""
    sys.exit("error: 没找到已打开的 X 标签页。先在 Chrome 里登录并打开 x.com，再重试。")


def fetch_cookies(tab_id: str) -> dict:
    found = {}
    for domain in (".x.com", ".twitter.com"):
        try:
            resp = _post("/api/cookies", {"domain": domain, "tabId": tab_id})
        except urllib.error.HTTPError as e:
            if e.code == 404:
                sys.exit(
                    "error: relay 没有 /api/cookies 路由。先打补丁再重启：\n"
                    "  node ops/patch-browser-relay.mjs && browser-relay restart"
                )
            raise
        for c in resp.get("cookies", []):
            name = c.get("name")
            if name in WANT and c.get("value"):
                found[name] = c["value"]
    return found


def mask(v: str) -> str:
    return f"{v[:2]}…{v[-2:]} (len={len(v)})" if len(v) > 6 else f"(len={len(v)})"


def main() -> int:
    ap = argparse.ArgumentParser(prog="x_cookies.py")
    ap.add_argument("--check", action="store_true", help="只检查能否提取，不写文件")
    args = ap.parse_args()

    tab_id = find_x_tab()
    found = fetch_cookies(tab_id)

    missing = [k for k in WANT if k not in found]
    if "auth_token" in missing:
        sys.exit(
            "error: 取到了部分 cookie 但没有 auth_token。"
            "多半是 X 未真正登录，或 relay 未打 /api/cookies 补丁（httpOnly 读不到）。\n"
            f"已取到：{sorted(found)}"
        )

    print("提取成功（仅显示掩码，未泄露值）：")
    for k in WANT:
        if k in found:
            print(f"  {k} = {mask(found[k])}")
    if missing:
        print(f"  注意：缺少 {missing}（last30days 可能仍可用，ct0 非必需）")

    if args.check:
        print("--check：未写文件")
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# papergirl X cookies — gitignored，0600。由 tools/x_cookies.py 生成。\n"]
    if "auth_token" in found:
        lines.append(f"AUTH_TOKEN={found['auth_token']}\n")
    if "ct0" in found:
        lines.append(f"CT0={found['ct0']}\n")
    OUT.write_text("".join(lines), encoding="utf-8")
    OUT.chmod(0o600)
    print(f"已写入 {OUT}（0600）。episode-runner 会自动 source。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
