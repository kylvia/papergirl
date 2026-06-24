"""WeChat 草稿箱发布适配器：vendored SDK + per-process 微信代理 + 文末关注卡。

从 push.py 原样抽出，行为不变。设计约束（不要破坏）：
  - 代理只注入本次 bun 子进程，不污染全局环境——AI/生图调用绝不走微信代理
  - 代理 filter 只放行微信域，正文引用的外域图片必须先下载到本地再 push
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path

from . import ROOT, PublishRequest

SDK = ROOT / 'vendor' / 'wechat-api' / 'wechat-api.ts'
# 固定关注卡片：推送时自动追加到正文末尾，保证每篇文末都有引导关注图。
# 入库于 assets/（非 gitignored），克隆即带；缺失则静默跳过，不阻塞推送。
FOLLOW_CARD = ROOT / 'assets' / 'follow-card.png'

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


def build_push_markdown(md: Path, enabled: bool):
    """在正文末尾追加固定关注卡片，返回 (要推送的 md, 待清理的临时文件 or None)。

    临时文件写在原 md 同目录，保留 baseDir——正文里相对路径的配图引用不被破坏；
    关注卡用绝对路径引用，与 baseDir 无关。幂等：正文已含关注卡（文件名命中）就原样推。
    关注卡资源缺失时静默降级，不阻塞推送。
    """
    if not enabled or not FOLLOW_CARD.exists():
        return md, None
    text = md.read_text(encoding='utf-8')
    if FOLLOW_CARD.name in text:
        return md, None
    footer = f'\n\n![扫码关注本公众号]({FOLLOW_CARD})\n'
    out = md.with_suffix('.push.md')
    out.write_text(text + footer, encoding='utf-8')
    return out, out


def publish(req: PublishRequest) -> int:
    app_id = os.environ.get('WECHAT_APP_ID', '')
    app_secret = os.environ.get('WECHAT_APP_SECRET', '')
    if not req.dry_run and (not app_id or not app_secret):
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
    if proxy and not req.dry_run:
        # bun >=1.3 在 subprocess 链路下只认小写 https_proxy，两种都给
        for key in ('https_proxy', 'HTTPS_PROXY', 'http_proxy', 'HTTP_PROXY'):
            env[key] = proxy

    push_md, tmp = build_push_markdown(req.md, enabled=req.follow_card)
    if tmp is not None and req.verbose:
        print(f'[push] 已在文末追加关注卡片 {FOLLOW_CARD.name}', file=sys.stderr)

    cmd = ['bun', str(SDK), str(push_md), '--theme', req.theme]
    if req.cover:
        cmd += ['--cover', str(Path(req.cover).expanduser().resolve())]
    if req.title:
        cmd += ['--title', req.title]
    if req.summary:
        cmd += ['--summary', req.summary]
    if req.author:
        cmd += ['--author', req.author]
    if req.dry_run:
        cmd += ['--dry-run']

    if req.verbose:
        shown = ' '.join(cmd)
        proxied = 'proxy=on' if (proxy and not req.dry_run) else 'proxy=off'
        print(f'$ {shown}  [{proxied}]', file=sys.stderr)

    # dry-run 是本地渲染，失败不该重试；真推时对代理瞬时抖动重试。
    try:
        if req.dry_run:
            return subprocess.call(cmd, env=env, cwd=str(ROOT))
        retries = int(os.environ.get('PUSH_RETRIES', '3'))
        delay = int(os.environ.get('PUSH_RETRY_DELAY', '60'))
        return _run_with_retry(cmd, env, retries, delay, req.verbose)
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)
