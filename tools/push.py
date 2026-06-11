#!/usr/bin/env python3
"""papergirl 推公众号草稿箱 — vendored WeChat SDK + per-process 微信代理。

配置（项目根 .env）：
  WECHAT_APP_ID / WECHAT_APP_SECRET   公众号凭证
  WECHAT_PROXY_URL                    微信 API 出站代理（IP 在公众号白名单）；留空走直连

设计约束（不要破坏）：
  - 代理只注入本次 bun 子进程，不污染全局环境——AI/生图调用绝不走微信代理
  - 代理 filter 只放行微信域，正文引用的外域图片必须先下载到本地再 push

用法：
  python3 tools/push.py drafts/x.md --title "标题" --cover drafts/x-cover.png [--theme default] [--summary ..] [--dry-run] [--verbose]
"""
import argparse
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SDK = ROOT / 'vendor' / 'wechat-api' / 'wechat-api.ts'

# 微信代理偶发瞬时抖动（CONNECT 隧道中止）。只对这类网络层错误重试；
# 撞到 40164 白名单 / 占位图 / token 这类逻辑错误立即失败，重试无意义。
_TRANSIENT_RE = re.compile(
    r'connect|tunnel|econnreset|econnrefused|etimedout|socket|fetch failed'
    r'|network|timed out|proxy|enotfound|eai_again|hang ?up',
    re.IGNORECASE,
)
_PERSISTENT_RE = re.compile(r'40164|errcode', re.IGNORECASE)


def is_transient_failure(output: str) -> bool:
    """非零退出时判断是否值得重试：命中网络签名且未命中明确的微信逻辑错误。"""
    if _PERSISTENT_RE.search(output):
        return False
    return bool(_TRANSIENT_RE.search(output))


def _run_with_retry(cmd: list, env: dict, retries: int, delay: int, verbose: bool) -> int:
    """跑推送子进程；网络瞬时失败时重试。捕获输出后回显，保留可见性。"""
    attempts = retries + 1
    for attempt in range(1, attempts + 1):
        proc = subprocess.run(cmd, env=env, cwd=str(ROOT), capture_output=True, text=True)
        sys.stdout.write(proc.stdout)
        sys.stderr.write(proc.stderr)
        if proc.returncode == 0:
            return 0
        combined = (proc.stdout or '') + (proc.stderr or '')
        if attempt < attempts and is_transient_failure(combined):
            print(
                f'[push] 推送失败（疑似代理瞬时抖动），{delay}s 后重试 '
                f'{attempt}/{retries} ...',
                file=sys.stderr,
            )
            time.sleep(delay)
            continue
        return proc.returncode
    return 1


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, _, value = line.partition('=')
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def main() -> int:
    load_dotenv(ROOT / '.env')
    ap = argparse.ArgumentParser(prog='push.py', description='push markdown to WeChat draft box')
    ap.add_argument('md')
    ap.add_argument('--title', default=None)
    ap.add_argument('--cover', default=None)
    ap.add_argument('--theme', default='grace')
    ap.add_argument('--summary', default=None)
    ap.add_argument('--author', default=None)
    ap.add_argument('--dry-run', action='store_true', help='只本地渲染，不调微信 API')
    ap.add_argument('--verbose', action='store_true')
    args = ap.parse_args()

    md = Path(args.md).expanduser().resolve()
    if not md.exists():
        print(f'error: {md} not found', file=sys.stderr)
        return 1

    app_id = os.environ.get('WECHAT_APP_ID', '')
    app_secret = os.environ.get('WECHAT_APP_SECRET', '')
    if not args.dry_run and (not app_id or not app_secret):
        print('error: WECHAT_APP_ID / WECHAT_APP_SECRET not configured (see .env.example)', file=sys.stderr)
        return 1

    node_modules = SDK.parent / 'node_modules'
    if not node_modules.is_dir():
        print(f'first-run: bun install in {SDK.parent} ...', file=sys.stderr)
        rc = subprocess.call(['bun', 'install'], cwd=str(SDK.parent))
        if rc != 0:
            return rc

    env = os.environ.copy()
    env['WECHAT_APP_ID'] = app_id
    env['WECHAT_APP_SECRET'] = app_secret

    proxy = os.environ.get('WECHAT_PROXY_URL', '')
    if proxy and not args.dry_run:
        # bun >=1.3 在 subprocess 链路下只认小写 https_proxy，两种都给
        for key in ('https_proxy', 'HTTPS_PROXY', 'http_proxy', 'HTTP_PROXY'):
            env[key] = proxy

    cmd = ['bun', str(SDK), str(md), '--theme', args.theme]
    if args.cover:
        cmd += ['--cover', str(Path(args.cover).expanduser().resolve())]
    if args.title:
        cmd += ['--title', args.title]
    if args.summary:
        cmd += ['--summary', args.summary]
    if args.author:
        cmd += ['--author', args.author]
    if args.dry_run:
        cmd += ['--dry-run']

    if args.verbose:
        shown = ' '.join(cmd)
        proxied = 'proxy=on' if (proxy and not args.dry_run) else 'proxy=off'
        print(f'$ {shown}  [{proxied}]', file=sys.stderr)

    # dry-run 是本地渲染，失败不该重试；真推时对代理瞬时抖动重试。
    if args.dry_run:
        return subprocess.call(cmd, env=env, cwd=str(ROOT))
    retries = int(os.environ.get('PUSH_RETRIES', '3'))
    delay = int(os.environ.get('PUSH_RETRY_DELAY', '60'))
    return _run_with_retry(cmd, env, retries, delay, args.verbose)


if __name__ == '__main__':
    sys.exit(main())
