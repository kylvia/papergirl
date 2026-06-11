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
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SDK = ROOT / 'vendor' / 'wechat-api' / 'wechat-api.ts'


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

    return subprocess.call(cmd, env=env, cwd=str(ROOT))


if __name__ == '__main__':
    sys.exit(main())
