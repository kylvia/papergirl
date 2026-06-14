#!/usr/bin/env python3
"""papergirl 源图抓取 — 从来源页提取高信息量图并落地 drafts/。

正文配图断点 a) 路径专用工具：发布 / 评测 / benchmark / 定价类选题，先尝试抓官方页
现成图（og:image、正文大图 / 图表），信息量够就用，抓不到再降级 cover.py 生成。
让"取源图"像 cover.py 一样一条命令。

硬约束（不要破坏）：
  - 绝不走微信代理：本工具在 episode 进程跑，进程本就无代理；代理是 per-process 给
    push.py 的。源图走直连——走代理 filter 只放行微信域，外域会被 403。
  - 垃圾图护栏：og:image 常是 1×1 像素 / logo / 报错页 HTML。content-type（按 magic
    bytes 认）、最小尺寸、最小字节任一不过关就拒，防垃圾图嵌进正文。
  - 版权边界（按一手性，调用方判断；本工具不替你判）：
      ✅ 一手官方源：厂商官博图、官网产品截图、官方 repo/docs 图表、benchmark 原图（注明来源）
      ⚠️ 第三方媒体自制题图 / 信息图：是该媒体作品，能避则避
      ❌ 个人社媒帖截图：不用

复用 cover.py 的下载逻辑（反 403 UA + 重试）与扩展名探测，不重复造轮子。

用法：
  python3 tools/fetch_source_image.py <page_url> --out drafts/x-fig-1.png [--verbose]
  python3 tools/fetch_source_image.py <img_url>  --out drafts/x-fig-1.png   # 直链图也行
  python3 tools/fetch_source_image.py <page_url> --dry-run                  # 只列候选，不下载

输出：最后一行 JSON。成功含 path / source_url / tier / width / height；
dry-run 含 candidates（按优先级 og > twitter > jsonld > article）。
抓不到 / 全被护栏拦下 → 非零退出，调用方据此降级到 cover.py 生成。
"""
import argparse
import html as _html
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit

# 复用 cover.py 的反 403 下载 + 扩展名探测，别重复造轮子
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cover import _download, detect_image_ext, save_image_with_detected_ext  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

DEFAULT_MIN_WIDTH = 320
DEFAULT_MIN_HEIGHT = 200
DEFAULT_MIN_BYTES = 5000
DEFAULT_TIMEOUT = 30

# 候选优先级：一手 meta 标注 > 正文 <img>
TIER_ORDER = {'og': 0, 'twitter': 1, 'jsonld': 2, 'article': 3}

# 正文 <img> 里按 URL 名称排掉的非内容图（og/twitter 是作者主动标注，不过滤）
_JUNK_NAME_RE = re.compile(
    r'logo|icon|favicon|sprite|avatar|spacer|pixel|blank|loading|placeholder|'
    r'badge|button|emoji|share|track|beacon|ad[-_/]',
    re.IGNORECASE,
)

_META_TAG_RE = re.compile(r'<meta\b[^>]*>', re.IGNORECASE)
_IMG_TAG_RE = re.compile(r'<img\b[^>]*>', re.IGNORECASE)
_LDJSON_RE = re.compile(
    r'<script[^>]+type\s*=\s*["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)
_ATTR_RE = re.compile(r'([\w:-]+)\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|([^\s>]+))')


def _attrs(tag: str) -> dict:
    out = {}
    for m in _ATTR_RE.finditer(tag):
        key = m.group(1).lower()
        val = m.group(2) if m.group(2) is not None else (m.group(3) if m.group(3) is not None else m.group(4))
        if key and val is not None and key not in out:
            out[key] = _html.unescape(val.strip())
    return out


def _abs(url: str, base: str) -> str:
    url = (url or '').strip()
    if not url:
        return ''
    if url.startswith('//'):
        scheme = urlsplit(base).scheme or 'https'
        return f'{scheme}:{url}'
    return urljoin(base, url)


def _pick_srcset(srcset: str) -> str:
    """从 srcset 取分辨率最高的一项；无宽度描述符则取第一项。"""
    best_url, best_w = '', -1
    for part in srcset.split(','):
        part = part.strip()
        if not part:
            continue
        bits = part.split()
        url = bits[0]
        w = -1
        if len(bits) > 1 and bits[1].endswith('w'):
            try:
                w = int(bits[1][:-1])
            except ValueError:
                w = -1
        # 第一项先兜底，再被更大宽度覆盖——否则只有密度描述符（1x/2x）或裸 URL 时 best_w 永远是 -1，返回空
        if not best_url or w > best_w:
            best_url, best_w = url, w
    return best_url


def _meta_images(html: str):
    for tag in _META_TAG_RE.findall(html):
        a = _attrs(tag)
        key = (a.get('property') or a.get('name') or '').lower()
        content = a.get('content', '')
        if not content:
            continue
        if key in ('og:image', 'og:image:secure_url', 'og:image:url'):
            yield 'og', content
        elif key in ('twitter:image', 'twitter:image:src'):
            yield 'twitter', content


def _jsonld_images(html: str):
    # in_image：只在「经由 image 键下钻」的上下文里取 url/contentUrl，避免把文章自身的
    # url（@type:Article 的 "url" 是正文链接，不是图）误当成图。比旧版「dict 必须
    # @type=ImageObject 才取 url」更鲁棒——很多站点的 image 直接是 {"url":..} 不带 @type。
    def walk(node, in_image=False):
        if isinstance(node, str):
            if in_image and node.strip():
                yield _html.unescape(node.strip())  # ld+json 里的 &amp; 等实体要还原，否则下载到错 URL
        elif isinstance(node, dict):
            img = node.get('image')
            if img is not None:
                yield from walk(img, True)
            if in_image:
                for k in ('url', 'contentUrl'):
                    if k in node:
                        yield from walk(node[k], True)
        elif isinstance(node, list):
            for x in node:
                yield from walk(x, in_image)

    for block in _LDJSON_RE.findall(html):
        try:
            data = json.loads(block.strip())
        except (ValueError, TypeError):
            continue
        for url in walk(data):
            yield 'jsonld', url


def _article_images(html: str):
    for tag in _IMG_TAG_RE.findall(html):
        a = _attrs(tag)
        # lazy-load 常把 data: 占位图塞进 src、真图放 data-src/data-original/srcset；
        # 逐个取第一个非 data: 的真实 URL，别被占位图截胡（取到 data: 就 continue 会丢掉整张真图）
        url = ''
        for cand in (a.get('src'), a.get('data-src'), a.get('data-original'),
                     _pick_srcset(a.get('srcset', '')) if a.get('srcset') else ''):
            if cand and not cand.strip().startswith('data:'):
                url = cand.strip()
                break
        if not url:
            continue
        if url.lower().split('?', 1)[0].endswith('.svg'):
            continue
        if _JUNK_NAME_RE.search(url):
            continue
        yield 'article', url


def gather_candidates(html: str, base_url: str) -> list:
    """按优先级返回去重后的候选图，每项 {url, tier}。"""
    raw = []
    raw.extend(_meta_images(html))
    raw.extend(_jsonld_images(html))
    raw.extend(_article_images(html))

    seen, out = set(), []
    for tier, url in raw:
        absurl = _abs(url, base_url)
        if not absurl or absurl.startswith('data:') or absurl in seen:
            continue
        seen.add(absurl)
        out.append({'url': absurl, 'tier': tier})
    out.sort(key=lambda c: TIER_ORDER.get(c['tier'], 99))
    return out


def image_dimensions(img: bytes):
    """不依赖 PIL，从 magic bytes 读宽高；读不出返回 None。"""
    n = len(img)
    if n >= 24 and img[:8] == b'\x89PNG\r\n\x1a\n':
        return int.from_bytes(img[16:20], 'big'), int.from_bytes(img[20:24], 'big')
    if n >= 10 and img[:6] in (b'GIF87a', b'GIF89a'):
        return int.from_bytes(img[6:8], 'little'), int.from_bytes(img[8:10], 'little')
    if n >= 2 and img[:2] == b'\xff\xd8':
        i = 2
        while i + 9 < n:
            if img[i] != 0xFF:
                i += 1
                continue
            marker = img[i + 1]
            if marker == 0xFF:
                i += 1
                continue
            if marker in (0xD8, 0xD9, 0x01) or 0xD0 <= marker <= 0xD7:
                i += 2
                continue
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                return int.from_bytes(img[i + 7:i + 9], 'big'), int.from_bytes(img[i + 5:i + 7], 'big')
            seg_len = int.from_bytes(img[i + 2:i + 4], 'big')
            if seg_len < 2:
                break
            i += 2 + seg_len
        return None
    if n >= 30 and img[:4] == b'RIFF' and img[8:12] == b'WEBP':
        fmt = img[12:16]
        if fmt == b'VP8 ':
            return int.from_bytes(img[26:28], 'little') & 0x3FFF, int.from_bytes(img[28:30], 'little') & 0x3FFF
        if fmt == b'VP8L':
            bits = int.from_bytes(img[21:25], 'little')
            return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
        if fmt == b'VP8X':
            return int.from_bytes(img[24:27], 'little') + 1, int.from_bytes(img[27:30], 'little') + 1
    return None


def passes_guards(img: bytes, min_w: int, min_h: int, min_bytes: int):
    """(ok, reason, dims)：magic 不是图 / 字节太小 / 尺寸太小 → 拦。读不出尺寸不拦（字节门兜底）。"""
    if not detect_image_ext(img):
        return False, 'not-an-image (bad magic bytes / likely HTML error page)', None
    if len(img) < min_bytes:
        return False, f'too-small {len(img)}B < {min_bytes}B', None
    dims = image_dimensions(img)
    if dims is not None:
        w, h = dims
        if w < min_w or h < min_h:
            return False, f'dimensions {w}x{h} < {min_w}x{min_h}', dims
    return True, '', dims


def main() -> int:
    ap = argparse.ArgumentParser(prog='fetch_source_image.py', description='fetch high-signal source image from a page')
    ap.add_argument('url', help='来源页 URL（或图片直链）')
    ap.add_argument('--out', help='落地路径（非 dry-run 必填），扩展名按真实格式修正')
    ap.add_argument('--min-width', type=int, default=DEFAULT_MIN_WIDTH)
    ap.add_argument('--min-height', type=int, default=DEFAULT_MIN_HEIGHT)
    ap.add_argument('--min-bytes', type=int, default=DEFAULT_MIN_BYTES)
    ap.add_argument('--timeout', type=int, default=DEFAULT_TIMEOUT)
    ap.add_argument('--dry-run', action='store_true', help='只列候选图 URL，不下载')
    ap.add_argument('--verbose', action='store_true')
    args = ap.parse_args()

    if not args.dry_run and not args.out:
        ap.error('--out is required unless --dry-run')

    def vlog(msg):
        if args.verbose:
            print(msg, file=sys.stderr)

    # 先抓原始字节：URL 本身就是图片（直链）则直接用，否则当 HTML 解析候选
    try:
        raw = _download(args.url, args.timeout)
    except Exception as e:
        print(json.dumps({'status': 'error', 'reason': f'fetch failed: {e}', 'url': args.url}, ensure_ascii=False))
        return 1

    if detect_image_ext(raw):
        candidates = [{'url': args.url, 'tier': 'direct'}]
        direct = raw
    else:
        html = raw.decode('utf-8', errors='replace')
        candidates = gather_candidates(html, args.url)
        direct = None
        vlog(f'[fetch] {len(candidates)} candidate(s) from {args.url}')

    if not candidates:
        print(json.dumps({'status': 'error', 'reason': 'no image candidates on page', 'url': args.url}, ensure_ascii=False))
        return 1

    if args.dry_run:
        print(json.dumps({'status': 'dry-run', 'url': args.url, 'candidates': candidates}, ensure_ascii=False))
        return 0

    # 按优先级逐个下载，第一个过护栏的就用
    tried = []
    for c in candidates:
        try:
            img = direct if (direct is not None and c['url'] == args.url) else _download(c['url'], args.timeout)
        except Exception as e:
            vlog(f'[skip] {c["url"]} -> download failed: {e}')
            tried.append({'url': c['url'], 'tier': c['tier'], 'reason': f'download failed: {e}'})
            continue
        ok, reason, dims = passes_guards(img, args.min_width, args.min_height, args.min_bytes)
        if not ok:
            vlog(f'[skip] {c["url"]} -> {reason}')
            tried.append({'url': c['url'], 'tier': c['tier'], 'reason': reason})
            continue
        saved = save_image_with_detected_ext(img, Path(args.out))
        w, h = dims if dims else (None, None)
        print(json.dumps({
            'status': 'fetched',
            'path': saved['path'],
            'ext': saved['ext'],
            'source_url': c['url'],
            'tier': c['tier'],
            'width': w,
            'height': h,
            'size_bytes': len(img),
        }, ensure_ascii=False))
        return 0

    print(json.dumps({
        'status': 'error',
        'reason': 'all candidates failed guards (too small / not an image / unreachable)',
        'url': args.url,
        'tried': tried,
    }, ensure_ascii=False))
    return 1


if __name__ == '__main__':
    sys.exit(main())
