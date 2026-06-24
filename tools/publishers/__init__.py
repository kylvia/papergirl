"""papergirl 发布适配器（publisher）seam。

push.py 是唯一入口（CLAUDE.md 硬规则 #7），按 PUBLISHER 分发到这里的某个适配器。
每个适配器是一个模块，暴露 `publish(req: PublishRequest) -> int`（返回退出码，0=成功）。

内置：
  wechat  默认。vendored WeChat SDK + per-process 微信代理 + 文末关注卡（原 push.py 逻辑，未变）。
  vault   零凭证、零依赖。把成稿导出成自包含 markdown bundle（note + frontmatter + 本地图片）。

加新适配器：本目录加 <name>.py 暴露 publish(req)，再在 get_publisher() 注册一行。
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# publishers → tools → repo 根
ROOT = Path(__file__).resolve().parents[2]


@dataclass
class PublishRequest:
    """一次推稿请求。各适配器按需取用，未用字段忽略。"""
    md: Path                 # 已 resolve 的成稿路径
    title: str | None
    summary: str | None
    cover: str | None        # 封面图路径（原样自 CLI，未 resolve）
    author: str | None
    theme: str
    dry_run: bool
    verbose: bool
    follow_card: bool        # 是否在文末追加关注卡（仅部分适配器支持，如 wechat）


def get_publisher(name: str):
    """按名字拿适配器模块（暴露 publish(req)->int）。未知名直接退出。"""
    key = (name or 'wechat').strip().lower()
    if key == 'wechat':
        from . import wechat
        return wechat
    if key == 'vault':
        from . import vault
        return vault
    raise SystemExit(f"error: 未知 PUBLISHER '{name}'（已知：wechat, vault）")
