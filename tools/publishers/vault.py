"""Vault 发布适配器（零凭证、零依赖）。

把成稿导出成一个自包含的 markdown bundle：note.md（带 frontmatter）+ assets/（封面与
正文本地图片）。让没有微信账号的环境也能跑通全流程，也是 files-first / Obsidian 视角的导出。

输出位置：$PAPERGIRL_VAULT_DIR（默认 <repo>/drafts/vault/），每篇一个子目录。
机器可读结果（stdout 末行）：`vault\t<note.md 路径>`。
"""
from __future__ import annotations

import datetime
import os
import re
import shutil
import sys
from pathlib import Path

from . import ROOT, PublishRequest

_FRONTMATTER_RE = re.compile(r'^---\n(.*?)\n---\n?', re.DOTALL)
_IMG_RE = re.compile(r'!\[([^\]]*)\]\(\s*([^)\s]+)(?:\s+"[^"]*")?\s*\)')


def _vault_dir() -> Path:
    override = os.environ.get('PAPERGIRL_VAULT_DIR', '').strip()
    return Path(override).expanduser() if override else ROOT / 'drafts' / 'vault'


def _split_frontmatter(text: str):
    """拆出成稿已有的 frontmatter（极简 key: value 解析）与正文。无则返回 ({}, 原文)。"""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    fm = {}
    for line in m.group(1).splitlines():
        if ':' in line and not line[:1].isspace() and not line.startswith('-'):
            k, _, v = line.partition(':')
            fm[k.strip()] = v.strip().strip('"').strip("'")
    return fm, text[m.end():]


def _yaml_str(v) -> str:
    return '"' + str(v).replace('\\', '\\\\').replace('"', '\\"') + '"'


def publish(req: PublishRequest) -> int:
    text = req.md.read_text(encoding='utf-8')
    src_fm, body = _split_frontmatter(text)

    title = req.title or src_fm.get('title') or req.md.stem
    summary = req.summary or src_fm.get('summary') or ''
    author = req.author or src_fm.get('author') or ''
    date = src_fm.get('date') or datetime.date.today().isoformat()

    bundle = _vault_dir() / req.md.stem
    assets = bundle / 'assets'

    copies = []          # (src_abs, dst_abs)
    used = set()

    def stage(src_path: Path, prefer: str | None = None) -> str | None:
        """登记一个本地资源待复制，返回改写后相对 note.md 的路径；不存在返回 None。"""
        if not src_path.exists():
            return None
        name = prefer or src_path.name
        base = name
        i = 1
        while name in used:
            dot = base.rfind('.')
            stem, ext = (base[:dot], base[dot:]) if dot > 0 else (base, '')
            name = f'{stem}-{i}{ext}'
            i += 1
        used.add(name)
        copies.append((src_path, assets / name))
        return f'assets/{name}'

    def repl(m):
        alt, src = m.group(1), m.group(2)
        if src.startswith(('http://', 'https://', 'data:')):
            return m.group(0)  # 外域 / 内联，保持原样
        p = Path(src) if os.path.isabs(src) else (req.md.parent / src)
        rel = stage(p.resolve())
        if rel is None:
            if req.verbose:
                print(f'[vault] 图片未找到，保持原引用: {src}', file=sys.stderr)
            return m.group(0)
        return f'![{alt}]({rel})'

    new_body = _IMG_RE.sub(repl, body).lstrip('\n')

    cover_rel = None
    if req.cover:
        cover_src = Path(req.cover).expanduser().resolve()
        cover_rel = stage(cover_src, prefer=f'cover{cover_src.suffix or ".png"}')
        if cover_rel is None and req.verbose:
            print(f'[vault] 封面未找到: {req.cover}', file=sys.stderr)

    fm_lines = ['---', f'title: {_yaml_str(title)}']
    if summary:
        fm_lines.append(f'summary: {_yaml_str(summary)}')
    if author:
        fm_lines.append(f'author: {_yaml_str(author)}')
    fm_lines.append(f'date: {date}')
    if cover_rel:
        fm_lines.append(f'cover: {cover_rel}')
    fm_lines += [f'theme: {req.theme}', f'source: {req.md.name}', 'publisher: vault', '---']
    note = '\n'.join(fm_lines) + '\n\n' + new_body

    note_path = bundle / 'note.md'

    if req.dry_run:
        print(f'[vault] dry-run：将写出 {note_path}（{len(copies)} 个资源 → {assets}/）', file=sys.stderr)
        if req.verbose:
            print('--- frontmatter ---\n' + '\n'.join(fm_lines), file=sys.stderr)
        print(f'vault\t{note_path}')
        return 0

    assets.mkdir(parents=True, exist_ok=True)
    for src_path, dst in copies:
        shutil.copy2(src_path, dst)
    note_path.write_text(note, encoding='utf-8')

    if req.verbose:
        print(f'[vault] 写出 {note_path}（{len(copies)} 个资源）', file=sys.stderr)
    print(f'vault\t{note_path}')
    return 0
