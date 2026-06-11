#!/usr/bin/env python3
"""papergirl · 公众号效果数据回流（人工喂，因为个人订阅号无 datacube API）。

个人订阅号拿不到微信数据 API（48001）。所以发布后由人从后台读几个数字贴回来，
本工具落盘并和 published.json 的选题特征对齐，供每周复盘学习用。

录入（发布 1-3 天后，数据稳定时）：
  python3 tools/metrics.py add --date 2026-06-11 --slot am \
      --read 1234 --look 56 --share 23 --like 18 --follow 9
  （read=阅读 look=在看 share=分享/转发 like=点赞 follow=涨粉；缺的留空）

查看排行（按质量加权信号，数据够了才有意义）：
  python3 tools/metrics.py report
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLISHED = ROOT / "state" / "published.json"
METRICS = ROOT / "state" / "metrics.json"


def load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []


def find_article(date: str, slot: str):
    for a in load(PUBLISHED):
        if a.get("date") == date and a.get("slot") == slot:
            return a
    return None


def cmd_add(args) -> int:
    art = find_article(args.date, args.slot)
    if not art:
        print(f"warn: published.json 里没有 {args.date}/{args.slot}，仍记录但缺特征对齐", file=sys.stderr)
    rec = {
        "date": args.date,
        "slot": args.slot,
        "title": (art or {}).get("title", ""),
        "topic": (art or {}).get("topic", ""),
        "beat": (art or {}).get("beat", ""),
        "archetype": (art or {}).get("archetype", ""),
        "read": args.read,
        "look": args.look,      # 在看
        "share": args.share,    # 分享/转发
        "like": args.like,      # 点赞
        "follow": args.follow,  # 涨粉
        "note": args.note,
    }
    data = [m for m in load(METRICS) if not (m.get("date") == args.date and m.get("slot") == args.slot)]
    data.append(rec)
    METRICS.parent.mkdir(parents=True, exist_ok=True)
    METRICS.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # 质量信号：在看率/分享率（除以阅读），是"看了不白看"的真实代理
    def rate(n):
        return f"{n / args.read * 100:.1f}%" if args.read and n is not None else "-"
    print(f"已记录 {args.date}/{args.slot}：阅读 {args.read} | 在看 {args.look}({rate(args.look)}) "
          f"| 分享 {args.share}({rate(args.share)}) | 涨粉 {args.follow}")
    return 0


def cmd_report(args) -> int:
    data = load(METRICS)
    if not data:
        print("还没有数据。发布后用 metrics.py add 录入。")
        return 0
    def look_rate(m):
        r, lk = m.get("read"), m.get("look")
        return (lk / r) if (r and lk is not None) else -1
    ranked = sorted(data, key=look_rate, reverse=True)
    print(f"{'日期':12} {'在看率':>7} {'阅读':>7} {'涨粉':>5}  标题")
    for m in ranked:
        lr = look_rate(m)
        lr_s = f"{lr*100:.1f}%" if lr >= 0 else "-"
        print(f"{m['date']}-{m.get('slot',''):2} {lr_s:>7} {str(m.get('read') or '-'):>7} "
              f"{str(m.get('follow') or '-'):>5}  {m.get('title','')[:30]}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(prog="metrics.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add")
    a.add_argument("--date", required=True)
    a.add_argument("--slot", required=True)
    for f in ("read", "look", "share", "like", "follow"):
        a.add_argument(f"--{f}", type=int, default=None)
    a.add_argument("--note", default="")
    a.set_defaults(func=cmd_add)
    r = sub.add_parser("report")
    r.set_defaults(func=cmd_report)
    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
