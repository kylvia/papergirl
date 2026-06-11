#!/usr/bin/env python3
"""papergirl · 每周效果复盘（质量加权北极星：在看率/分享率/涨粉）。

读 state/metrics.json（人工喂的数据）+ published.json（选题特征），
按赛道/文章原型聚合质量信号，指出谁系统性偏高偏低 → 给调整建议。

刻意只报告+建议，不自动改 beats.yaml/voice.md：早期样本小，自动调权重会学到噪声
（见 CLAUDE.md 的冷启动告诫）。建议由人/agent 看过再决定是否采纳。

用法：
  python3 tools/review.py            # 复盘报告
  python3 tools/review.py --min 8    # 自定义"够不够学"的样本阈值（默认 8）
"""
import argparse
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
METRICS = ROOT / "state" / "metrics.json"


def load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []


def look_rate(m):
    r, lk = m.get("read"), m.get("look")
    return (lk / r) if (r and lk is not None) else None


def share_rate(m):
    r, sh = m.get("read"), m.get("share")
    return (sh / r) if (r and sh is not None) else None


def group_stats(rows, key, value_fn):
    buckets = defaultdict(list)
    for m in rows:
        v = value_fn(m)
        k = m.get(key)
        if v is not None and k:
            buckets[k].append(v)
    out = []
    for k, vals in buckets.items():
        out.append((k, statistics.mean(vals), len(vals)))
    return sorted(out, key=lambda x: x[1], reverse=True)


def main() -> int:
    ap = argparse.ArgumentParser(prog="review.py")
    ap.add_argument("--min", type=int, default=8, help="开始给方向性建议的最小样本量")
    args = ap.parse_args()

    rows = load(METRICS)
    n = len(rows)
    print(f"== papergirl 复盘 ==  已录入 {n} 篇\n")
    if n == 0:
        print("还没数据。发布后用 tools/metrics.py add 录入。")
        return 0

    # 总览：质量信号排行（始终可看）
    overall_look = [look_rate(m) for m in rows if look_rate(m) is not None]
    if overall_look:
        print(f"全局在看率：均值 {statistics.mean(overall_look)*100:.1f}% | "
              f"区间 {min(overall_look)*100:.1f}%–{max(overall_look)*100:.1f}%")
    ranked = sorted([m for m in rows if look_rate(m) is not None], key=look_rate, reverse=True)
    print("\n按在看率（看了不白看的代理）：")
    for m in ranked[:10]:
        print(f"  {look_rate(m)*100:5.1f}%  涨粉 {str(m.get('follow') or '-'):>4}  {m.get('title','')[:34]}")

    if n < args.min:
        print(f"\n样本 {n} < {args.min}，还不够做赛道/原型归因——继续攒。"
              f"早期只看单篇排行 + 你的口味判断，别急着调权重（会学到噪声）。")
        return 0

    # 够样本了：按赛道、原型聚合
    print("\n— 按赛道（在看率均值，样本数）—")
    for k, mean, c in group_stats(rows, "beat", look_rate):
        print(f"  {mean*100:5.1f}%  (n={c})  {k}")
    print("\n— 按文章原型（在看率均值，样本数）—")
    for k, mean, c in group_stats(rows, "archetype", look_rate):
        print(f"  {mean*100:5.1f}%  (n={c})  {k}")

    print("\n建议（人工确认后再改 beats.yaml / voice.md）：")
    beat_stats = group_stats(rows, "beat", look_rate)
    if len(beat_stats) >= 2:
        hi, lo = beat_stats[0], beat_stats[-1]
        if hi[2] >= 2 and lo[2] >= 2:
            print(f"  · 赛道「{hi[0]}」在看率最高({hi[1]*100:.1f}%)，可在 beats.yaml 上调权重")
            print(f"  · 赛道「{lo[0]}」最低({lo[1]*100:.1f}%)，考虑降权或换切口")
    print("  · 把在看率最高的几篇标题，归纳成范式回填 voice.md 的标题/开头范文库")
    return 0


if __name__ == "__main__":
    sys.exit(main())
