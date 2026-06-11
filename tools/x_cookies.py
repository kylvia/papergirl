#!/usr/bin/env python3
"""papergirl · 提取 X 登录 cookie 给 last30days 用（auth_token + ct0）。

走 last30days 自带的原生提取（vendored 在 .claude/skills/last30days/scripts/lib）：
直接读浏览器的 Cookies SQLite 库 + macOS Keychain 解密，能拿到 httpOnly cookie
（httpOnly 只挡页面 JS，不挡磁盘读取）。无需 browser-relay，无需改任何全局包。

前置：macOS + 用 Chrome（或 Brave/Firefox/Safari）登录过 X。

做什么：提取 auth_token + ct0 → 写进 gitignored 的 state/x-cookies.env（0600）。
episode-runner.sh 自动 source，把 AUTH_TOKEN/CT0 传给 last30days。失效就重跑本脚本。

安全：auth_token 是密码级凭证。只写进 0600 文件，绝不打印其值（成功只回显掩码）。

用法：
  python3 tools/x_cookies.py                 # 提取并写入（browser=auto）
  python3 tools/x_cookies.py --check         # 只验证能否提取，不写文件
  python3 tools/x_cookies.py --browser chrome  # 指定浏览器（chrome/brave/firefox/safari/auto）
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LAST30DAYS_LIB = ROOT / ".claude" / "skills" / "last30days" / "scripts"
OUT = ROOT / "state" / "x-cookies.env"
WANT = ["auth_token", "ct0"]
X_DOMAIN = ".x.com"


def mask(v: str) -> str:
    return f"{v[:2]}…{v[-2:]} (len={len(v)})" if len(v) > 6 else f"(len={len(v)})"


def main() -> int:
    ap = argparse.ArgumentParser(prog="x_cookies.py")
    ap.add_argument("--check", action="store_true", help="只验证能否提取，不写文件")
    ap.add_argument("--browser", default="auto",
                    choices=["auto", "chrome", "brave", "firefox", "safari"])
    args = ap.parse_args()

    sys.path.insert(0, str(LAST30DAYS_LIB))
    try:
        from lib.cookie_extract import extract_cookies_with_source
    except Exception as e:
        sys.exit(f"error: 无法加载 last30days cookie 模块（{LAST30DAYS_LIB}）：{e}")

    result = extract_cookies_with_source(args.browser, X_DOMAIN, WANT)
    if not result:
        sys.exit(
            "error: 没提取到 X cookie。检查：1) 是否 macOS；2) 用 --browser 指定的浏览器"
            "是否登录过 x.com；3) Keychain 是否放行（首次可能弹窗，点允许）。"
        )
    found, source = result
    found = found or {}

    if "auth_token" not in found:
        sys.exit(
            f"error: 从 {source} 取到了部分 cookie 但没有 auth_token，多半是该浏览器未真正登录 X。\n"
            f"已取到：{sorted(found)}"
        )

    print(f"提取成功（来源：{source}；仅显示掩码，未泄露值）：")
    for k in WANT:
        if k in found:
            print(f"  {k} = {mask(found[k])}")
    missing = [k for k in WANT if k not in found]
    if missing:
        print(f"  注意：缺少 {missing}（ct0 非必需，last30days 可能仍可用）")

    if args.check:
        print("--check：未写文件")
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# papergirl X cookies — gitignored，0600。由 tools/x_cookies.py 生成。\n"]
    for k in WANT:
        if k in found:
            lines.append(f"{k.upper()}={found[k]}\n")
    OUT.write_text("".join(lines), encoding="utf-8")
    OUT.chmod(0o600)
    print(f"已写入 {OUT}（0600）。episode-runner 会自动 source。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
