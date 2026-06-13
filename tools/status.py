#!/usr/bin/env python3
"""papergirl · 一屏状态：今天跑了吗 / 草稿箱 / 下次几点 / 该喂哪篇 / X 通不通。

接手先跑 `bin/status.sh`，免得每次手敲 parse jsonl/published/runs。数据源都是现成的
盘上文件 + `paseo schedule ls`，**只读不改**。
"""
import json
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CN = timezone(timedelta(hours=8))  # 北京固定 UTC+8，免 zoneinfo 依赖
G, Y, R, B, N = "\033[32m", "\033[33m", "\033[31m", "\033[1m", "\033[0m"


def now_cn():
    return datetime.now(timezone.utc).astimezone(CN)


def load(rel, default):
    try:
        return json.loads((ROOT / rel).read_text(encoding="utf-8"))
    except Exception:
        return default


def head(t):
    print(f"\n{B}▸ {t}{N}")


def main():
    today = now_cn().strftime("%Y-%m-%d")
    print(f"{B}papergirl 状态 · {now_cn():%Y-%m-%d %H:%M} 北京{N}")

    # 今日运行
    head(f"今日运行（{today}）")
    runs = sorted((ROOT / "state" / "runs").glob(f"{today}-*.json"))
    if not runs:
        print("  （今天还没跑）")
    for f in runs:
        try:
            r = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        st = r.get("status", "?")
        c = G if st in ("pushed", "dry-run") else (Y if st == "skipped" else R)
        mid = "media_id ✓" if r.get("media_id") else ""
        print(f"  {c}{r.get('slot', '?'):5}{N} {st:8} 《{r.get('title', '')[:28]}》 {mid}")

    # 最近发布 / 草稿箱
    head("最近发布（published.json 末 4 条）")
    pub = load("state/published.json", [])
    for i, e in enumerate(pub[-4:][::-1]):
        tag = f"  {Y}← 最新，去后台终审+群发{N}" if i == 0 else ""
        print(f"  {e.get('date')} {e.get('slot', '?'):4} 《{e.get('title', '')[:26]}》{tag}")

    # 定时档下次运行
    head("定时档下次运行（北京时）")
    try:
        out = subprocess.run(["paseo", "schedule", "ls", "--json"],
                             capture_output=True, text=True, timeout=10).stdout
        rows = []
        for s in json.loads(out or "[]"):
            nr = s.get("nextRunAt")
            if nr:
                rows.append((datetime.fromisoformat(nr.replace("Z", "+00:00")), s.get("name", "?")))
        for dt, name in sorted(rows):
            mins = int((dt - datetime.now(timezone.utc)).total_seconds() // 60)
            rel = f"{mins // 60}h{mins % 60}m 后" if mins > 0 else "已过/补跑中"
            print(f"  {name:14} {dt.astimezone(CN):%m-%d %H:%M}  ({rel})")
        if not rows:
            print(f"  {Y}（无定时档，跑 bin/bootstrap.sh 建）{N}")
    except Exception as e:
        print(f"  {R}paseo 不可达：{e}{N}")

    # 待喂数据
    head("待喂数据（发布满 2 天没 metrics）")
    try:
        out = subprocess.run([sys.executable, str(ROOT / "tools" / "metrics_nudge.py"), "--dry-run", "--days", "2"],
                             capture_output=True, text=True, timeout=15).stdout.strip()
        if "无待喂数据" in out or not out:
            print(f"  {G}✓ 都喂了{N}")
        else:
            for line in out.splitlines():
                if line.startswith("·") or "篇发布已满" in line:
                    print(f"  {Y}{line}{N}")
    except Exception as e:
        print(f"  ?（{e}）")

    # X 源
    head("X 源")
    cookie = (ROOT / "state" / "x-cookies.env").exists()
    try:
        nv = subprocess.run(["node", "-v"], capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception:
        nv = "?"
    if cookie:
        print(f"  {G}✓ cookie 在{N} · node {nv}（`bin/doctor.sh --x` 真拉验证）")
    else:
        print(f"  {Y}⚠ 无 cookie，X 降级跳过{N} · node {nv}（tools/x_cookies.py 启用）")
    print()


if __name__ == "__main__":
    main()
