#!/usr/bin/env python3
"""papergirl 推稿入口 — 按 PUBLISHER 分发到具体发布适配器（tools/publishers/）。

适配器：
  wechat  默认。vendored WeChat SDK + per-process 微信代理 + 文末关注卡（原逻辑，行为不变）。
  vault   零凭证。把成稿+frontmatter+本地图片导出成自包含 markdown bundle。

选择：--publisher，或环境变量 PUBLISHER（默认 wechat）。

硬规则：推送只走本入口（CLAUDE.md #7）；凭证只在 .env；只进草稿箱不群发。

用法：
  python3 tools/push.py drafts/x.md --title "标题" --cover drafts/x-cover.png [--summary ..] [--dry-run] [--verbose]
  PUBLISHER=vault python3 tools/push.py drafts/x.md --title "标题" --cover drafts/x-cover.png
"""
import argparse
import os
import sys
from pathlib import Path

from publishers import PublishRequest, get_publisher

ROOT = Path(__file__).resolve().parent.parent


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
    ap = argparse.ArgumentParser(prog='push.py', description='push markdown via the configured publisher')
    ap.add_argument('md')
    ap.add_argument('--title', default=None)
    ap.add_argument('--cover', default=None)
    ap.add_argument('--theme', default='grace')
    ap.add_argument('--summary', default=None)
    ap.add_argument('--author', default=None)
    ap.add_argument('--dry-run', action='store_true', help='只本地渲染/导出，不调外部 API')
    ap.add_argument('--no-follow-card', action='store_true', help='本次推送不追加固定关注卡片（仅 wechat）')
    ap.add_argument('--publisher', default=None,
                    help='发布适配器 wechat|vault（默认取环境变量 PUBLISHER，再默认 wechat）')
    ap.add_argument('--verbose', action='store_true')
    args = ap.parse_args()

    md = Path(args.md).expanduser().resolve()
    if not md.exists():
        print(f'error: {md} not found', file=sys.stderr)
        return 1

    req = PublishRequest(
        md=md,
        title=args.title,
        summary=args.summary,
        cover=args.cover,
        author=args.author,
        theme=args.theme,
        dry_run=args.dry_run,
        verbose=args.verbose,
        follow_card=not args.no_follow_card,
    )

    name = args.publisher or os.environ.get('PUBLISHER', 'wechat')
    return get_publisher(name).publish(req)


if __name__ == '__main__':
    sys.exit(main())
