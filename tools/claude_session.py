"""Claude stream-json 输出解析 + episode 运行记录。

来源：JimLiu/baoyu-skills 的 claude_session.py，papergirl 裁剪为：
  - _extract: stream-json 行 → (session_id, final_text)
  - extract_json: 宽松 JSON 抠取（容忍围栏/前后说明文字）
  - record 子命令: 解析 episode 日志 → 写 state/runs/<date>-<slot>.json，
    stdout 输出 tab 分隔的 status/session_id/title/media_id 给 runner。
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


def _extract(lines: list) -> tuple:
    """从 stream-json 行里提 (session_id, final_text)。"""
    session_id = None
    final_text = ""
    last_assistant_text = ""
    for line in lines:
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if session_id is None:
            sid = ev.get("session_id")
            if sid:
                session_id = sid
        etype = ev.get("type")
        if etype == "assistant":
            for block in (ev.get("message") or {}).get("content") or []:
                if block.get("type") == "text":
                    last_assistant_text = block.get("text", "")
        elif etype == "result":
            r = ev.get("result")
            if isinstance(r, str) and r.strip():
                final_text = r
    return session_id, (final_text or last_assistant_text)


_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.+?)\s*```", re.DOTALL)


def extract_json(text: str) -> Optional[dict]:
    """从 AI 输出里抠出 JSON 对象（容忍 ```json 围栏 / 前后说明文字）。"""
    if not text:
        return None
    text = text.strip()
    m = _JSON_FENCE_RE.search(text)
    if m:
        text = m.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def record(log_path: str, out_path: str, date: str, slot: str, rc: int) -> int:
    try:
        lines = Path(log_path).read_text(encoding="utf-8").splitlines()
    except OSError:
        lines = []
    session_id, final_text = _extract(lines)
    final = extract_json(final_text) or {}

    status = str(final.get("status") or "")
    if not status:
        status = "error" if rc != 0 else "unknown"

    rec = {
        "date": date,
        "slot": slot,
        "rc": rc,
        "status": status,
        "session_id": session_id or "",
        "title": str(final.get("title") or ""),
        "slug": str(final.get("slug") or ""),
        "media_id": str(final.get("media_id") or ""),
        "draft_path": str(final.get("draft_path") or ""),
        "reason": str(final.get("reason") or ""),
        "finished_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "log": log_path,
    }
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def g(value: str) -> str:
        return value.replace("\t", " ").replace("\n", " ").strip() or "-"

    print("\t".join([g(status), g(rec["session_id"]), g(rec["title"]), g(rec["media_id"])]))
    return 0


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    pr = sub.add_parser("record")
    pr.add_argument("--log", required=True)
    pr.add_argument("--out", required=True)
    pr.add_argument("--date", required=True)
    pr.add_argument("--slot", required=True)
    pr.add_argument("--rc", type=int, required=True)
    pe = sub.add_parser("extract-json")
    pe.add_argument("text")
    args = ap.parse_args()
    if args.cmd == "record":
        sys.exit(record(args.log, args.out, args.date, args.slot, args.rc))
    if args.cmd == "extract-json":
        print(json.dumps(extract_json(args.text), ensure_ascii=False, indent=2))
