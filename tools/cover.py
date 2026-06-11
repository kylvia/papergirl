#!/usr/bin/env python3
"""papergirl 封面/配图生成 — OpenAI-compatible chat/completions 生图网关。

配置（项目根 .env 或环境变量）：
  IMAGE_API_URL   生图网关地址（chat/completions 端点）
  IMAGE_API_KEY   API key
  IMAGE_MODEL     模型名（默认 gpt-image-2）

用法：
  python3 tools/cover.py --title "标题" [--subtitle "副标题"] [--summary "文章核心论点"] \
      [--style minimal-tech|editorial] --out drafts/x.png
  python3 tools/cover.py --prompt "完整生图 prompt" --out drafts/x.png
  加 --dry-run 只渲染 prompt 不调 API。

输出：最后一行 JSON，其中 "path" 是实际保存路径——扩展名按图片真实格式修正，
后续引用必须用这个 path，不要用 --out 原样路径。
"""
import argparse
import base64
import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

try:
    import httpx as _httpx
except ImportError:
    _httpx = None

ROOT = Path(__file__).resolve().parent.parent
PRESETS_DIR = Path(__file__).resolve().parent / 'presets'

DEFAULT_MODEL = 'gpt-image-2'
DEFAULT_ASPECT = '2.35:1'  # 公众号封面 900x383
DEFAULT_BRAND_COLOR = '#8087EA'


def load_dotenv(path: Path) -> None:
    """把 .env 里的 KEY=VALUE 灌进 os.environ（已存在的不覆盖）。"""
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


def detect_image_ext(img: bytes) -> str:
    if len(img) >= 4 and img[0:4] == b'\x89PNG':
        return 'png'
    if len(img) >= 3 and img[0:3] == b'\xff\xd8\xff':
        return 'jpg'
    if len(img) >= 12 and img[0:4] == b'RIFF' and img[8:12] == b'WEBP':
        return 'webp'
    if len(img) >= 4 and img[0:4] == b'GIF8':
        return 'gif'
    return ''


def save_image_with_detected_ext(img: bytes, out_path: Path, declared_ext: str = '') -> dict:
    out_path = Path(out_path)
    detected = detect_image_ext(img)
    ext = detected or declared_ext.lower().lstrip('.') or out_path.suffix.lower().lstrip('.') or 'png'
    if ext == 'jpeg':
        ext = 'jpg'
    final_path = out_path if out_path.suffix.lower() == f'.{ext}' else out_path.with_suffix(f'.{ext}')
    final_path.parent.mkdir(parents=True, exist_ok=True)
    final_path.write_bytes(img)
    return {'path': str(final_path), 'ext': ext}


def build_prompt(title: str, subtitle: str, summary: str, bullets: list, style: str) -> str:
    path = PRESETS_DIR / f'{style}.txt'
    if not path.exists():
        available = sorted(p.stem for p in PRESETS_DIR.glob('*.txt'))
        sys.exit(f'error: preset "{style}" not found. available: {available}')
    template = path.read_text(encoding='utf-8')
    bullets_str = '、'.join(f'"• {b}"' for b in bullets) if bullets else '不要底部数据条'
    out = template
    for key, value in (
        ('title', title),
        ('subtitle', subtitle),
        ('summary', summary or subtitle or title),
        ('bullets_str', bullets_str),
        ('style', style),
        ('aspect_ratio', os.environ.get('COVER_ASPECT_RATIO', DEFAULT_ASPECT)),
        ('brand_color', os.environ.get('COVER_BRAND_COLOR', DEFAULT_BRAND_COLOR)),
    ):
        out = out.replace('{%s}' % key, value)
    return out


def _post_json(api_url: str, headers: dict, body: dict, timeout: int) -> dict:
    # 网关偶发在 POST 后 ~3s 断开首个连接，重试通常立刻成功；httpx 比 urllib 稳定。
    if _httpx is not None:
        last_exc = None
        for _ in range(3):
            try:
                with _httpx.Client(timeout=timeout) as c:
                    resp = c.post(api_url, headers=headers, json=body)
                    resp.raise_for_status()
                    return resp.json()
            except (_httpx.RemoteProtocolError, _httpx.ReadError) as e:
                last_exc = e
                continue
        raise RuntimeError(f'all 3 attempts failed: {last_exc}')
    req = urllib.request.Request(api_url, method='POST', headers=headers, data=json.dumps(body).encode())
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


_DL_HEADERS = {
    # 网关图床 CDN 会 403 掉默认的 python-httpx/urllib UA
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36',
    'Accept': 'image/*,*/*;q=0.8',
}


def _download(url: str, timeout: int) -> bytes:
    last_exc = None
    for _ in range(3):
        try:
            if _httpx is not None:
                with _httpx.Client(timeout=timeout, follow_redirects=True, headers=_DL_HEADERS) as c:
                    r = c.get(url)
                    r.raise_for_status()
                    if r.content:
                        return r.content
            else:
                req = urllib.request.Request(url, headers=_DL_HEADERS)
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    data = r.read()
                    if data:
                        return data
        except Exception as e:
            last_exc = e
            continue
    raise RuntimeError(f'image download failed after 3 attempts: {last_exc}')


def generate_image(prompt: str, out_path: Path, timeout: int = 180) -> dict:
    api_url = os.environ.get('IMAGE_API_URL')
    api_key = os.environ.get('IMAGE_API_KEY')
    if not api_url or not api_key:
        sys.exit('error: IMAGE_API_URL / IMAGE_API_KEY not configured (see .env.example)')
    model = os.environ.get('IMAGE_MODEL', DEFAULT_MODEL)

    headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
    body = {'model': model, 'messages': [{'role': 'user', 'content': prompt}], 'temperature': 1, 'stream': False}

    t0 = time.time()
    data = _post_json(api_url, headers, body, timeout)
    dt = time.time() - t0

    content = data['choices'][0]['message']['content']
    # 已知两种返回：base64 data URI 内联，或 markdown 图链
    m_b64 = re.search(r'data:image/(\w+);base64,([A-Za-z0-9+/=]+)', content)
    m_url = re.search(r'!\[[^\]]*\]\((https?://[^\s)]+)\)', content)

    if m_b64:
        ext, b64 = m_b64.group(1), m_b64.group(2)
        img = base64.b64decode(b64)
    elif m_url:
        url = m_url.group(1)
        ext = url.rsplit('.', 1)[-1].split('?', 1)[0].lower()
        if ext not in ('png', 'jpg', 'jpeg', 'webp'):
            ext = 'png'
        img = _download(url, timeout)
    else:
        raise RuntimeError(f'no image in response. Head: {content[:200]}')

    saved = save_image_with_detected_ext(img, Path(out_path), ext)
    return {
        'path': saved['path'],
        'ext': saved['ext'],
        'size_bytes': len(img),
        'duration_sec': round(dt, 2),
        'model': data.get('model', model),
    }


def main() -> int:
    load_dotenv(ROOT / '.env')
    ap = argparse.ArgumentParser(prog='cover.py', description='papergirl image generation')
    ap.add_argument('--title', default='')
    ap.add_argument('--subtitle', default='')
    ap.add_argument('--summary', default='', help='文章核心论点，驱动封面视觉构思（不渲染到图上）')
    ap.add_argument('--bullets', action='append', default=[], help='可重复；底部数据条文字')
    ap.add_argument('--style', default='minimal-tech')
    ap.add_argument('--prompt', default='', help='完整 prompt，给了就忽略 title/style 模板')
    ap.add_argument('--out', required=True)
    ap.add_argument('--timeout', type=int, default=180)
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    if not args.prompt and not args.title:
        ap.error('need --title or --prompt')
    prompt = args.prompt or build_prompt(args.title, args.subtitle, args.summary, args.bullets, args.style)

    if args.dry_run:
        print(json.dumps({'action': 'dry-run', 'prompt_length': len(prompt), 'out': args.out}, ensure_ascii=False))
        return 0

    result = generate_image(prompt, Path(args.out), timeout=args.timeout)
    print(json.dumps({'action': 'generated', **result}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
