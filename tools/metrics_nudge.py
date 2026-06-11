#!/usr/bin/env python3
"""papergirl · 催数据提醒（单向，复用飞书嗓子）。

扫 published.json，找出"发布满 N 天但 metrics.json 里还没数据"的文章，
有就推一条飞书提醒。由 paseo 每天跑一次。

published.json 的 date 是 episode 出稿日；真实群发由人手动、时间不定，
所以这里用"出稿满 N 天仍无 metrics"近似"早该有数据了"。人若当天没发，
收到提醒时确认已发再喂即可；没发就忽略。

用法：
  python3 tools/metrics_nudge.py            # 默认满 2 天
  python3 tools/metrics_nudge.py --days 3
  python3 tools/metrics_nudge.py --dry-run  # 只打印不推
"""
import argparse
import json
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLISHED = ROOT / "state" / "published.json"
METRICS = ROOT / "state" / "metrics.json"


def load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []


def main() -> int:
    ap = argparse.ArgumentParser(prog="metrics_nudge.py")
    ap.add_argument("--days", type=int, default=2, help="出稿满几天仍无数据就提醒")
    ap.add_argument("--today", default="", help="覆盖今天日期 YYYY-MM-DD（测试用）")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    today = datetime.strptime(args.today, "%Y-%m-%d").date() if args.today else date.today()
    have = {(m.get("date"), m.get("slot")) for m in load(METRICS)}

    missing = []
    for a in load(PUBLISHED):
        d, slot = a.get("date"), a.get("slot")
        if not a.get("media_id"):
            continue  # 没真推成功的不催
        try:
            age = (today - datetime.strptime(d, "%Y-%m-%d").date()).days
        except (TypeError, ValueError):
            continue
        if age >= args.days and (d, slot) not in have:
            missing.append((d, slot, a.get("title", "")))

    if not missing:
        print("无待喂数据。")
        return 0

    lines = [f"📊 papergirl 催数据：{len(missing)} 篇发布已满 {args.days} 天还没喂效果数据，记得补："]
    for d, slot, title in missing[:8]:
        lines.append(f"· {d}-{slot}《{title[:24]}》")
    lines.append("喂法：tools/metrics.py add --date <d> --slot <slot> --read .. --look .. --share .. --follow ..")
    msg = "\n".join(lines)

    if args.dry_run:
        print(msg)
        return 0
    subprocess.run([sys.executable, str(ROOT / "tools" / "notify.py"), msg], check=False)
    print(f"已提醒 {len(missing)} 篇。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
