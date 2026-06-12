#!/usr/bin/env python3
"""papergirl · 定时档对账引擎（声明式）。

schedules.yaml 是源真相；这里把它 apply 到 paseo 现网、或 check 现网是否符合。
bootstrap.sh 用 apply，doctor.sh 用 check。两端共用同一份比对逻辑，杜绝漂移。

为什么存在：CLAUDE.md 曾手写一张「schedule id 表」，迁移一次就全作废（id 由 paseo
运行时分配）。手写的事实必腐烂——所以 id 不写死、现查；约束（尤其 mode=bypassPermissions
这条血泪坑）由本脚本在 apply/check 两端强制，不再靠人记。

用法：
  python3 tools/schedules.py check    # 校验现网符合 schedules.yaml（不符 → exit 1）
  python3 tools/schedules.py apply    # 让现网对齐 schedules.yaml（缺则建、漂移则修）
  python3 tools/schedules.py ls       # 现网档一览（带现网 id）
"""
import json
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("error: 需要 pyyaml（pip install pyyaml，或先跑 bin/bootstrap.sh）")

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "schedules.yaml"

OK, WARN, BAD = "\033[32m✓\033[0m", "\033[33m⚠\033[0m", "\033[31m✗\033[0m"


def paseo(*args, check=True):
    """跑一条 paseo 子命令，返回 (rc, stdout)。check=True 时失败抛异常。"""
    r = subprocess.run(["paseo", *args], capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"paseo {' '.join(args)} 失败：{r.stderr.strip() or r.stdout.strip()}")
    return r.returncode, r.stdout


def load_spec():
    doc = yaml.safe_load(SPEC.read_text(encoding="utf-8"))
    defaults = doc.get("defaults", {})
    specs = []
    for s in doc.get("schedules", []):
        specs.append({
            "name": s["name"],
            "cron": str(s["cron"]),
            "prompt": s["prompt"].rstrip("\n"),
            "provider": s.get("provider", defaults.get("provider", "claude")),
            "mode": s.get("mode", defaults.get("mode", "bypassPermissions")),
            "timezone": s.get("timezone", defaults.get("timezone", "UTC")),
        })
    return specs


def live_list():
    """现网档：{name: {id, cadence, status}}（按 name 索引，name 是我们的对账键）。"""
    _, out = paseo("schedule", "ls", "--json")
    return {s["name"]: s for s in json.loads(out or "[]")}


def live_mode(sid):
    _, out = paseo("schedule", "inspect", sid, "--json")
    return (json.loads(out).get("target", {}).get("config", {}) or {}).get("modeId")


def cmd_check():
    specs, live = load_spec(), live_list()
    problems = 0
    for sp in specs:
        cur = live.get(sp["name"])
        if not cur:
            print(f"  {BAD} {sp['name']}：现网缺失")
            problems += 1
            continue
        bits = []
        if cur.get("status") != "active":
            bits.append(f"{BAD} status={cur.get('status')}")
            problems += 1
        mode = live_mode(cur["id"])
        if mode != sp["mode"]:
            bits.append(f"{BAD} mode={mode}（应 {sp['mode']}）")
            problems += 1
        want_cad = f"cron:{sp['cron']} ({sp['timezone']})"
        if cur.get("cadence") != want_cad:
            bits.append(f"{WARN} cadence={cur.get('cadence')}（声明 {want_cad}）")
        tail = "  ".join(bits) if bits else f"{OK} active mode={mode}"
        print(f"  {OK if not bits or all(WARN in b for b in bits) else BAD} {sp['name']} [{cur['id']}]  {tail}")
    extras = set(live) - {s["name"] for s in specs}
    for name in sorted(extras):
        print(f"  {WARN} 现网多出未声明的档：{name} [{live[name]['id']}]（不动它，自行确认）")
    return 1 if problems else 0


def cmd_apply():
    specs, live = load_spec(), live_list()
    changed = 0
    for sp in specs:
        cur = live.get(sp["name"])
        if not cur:
            paseo("schedule", "create", sp["prompt"],
                  "--name", sp["name"], "--cron", sp["cron"],
                  "--timezone", sp["timezone"], "--provider", sp["provider"],
                  "--mode", sp["mode"], "--cwd", str(ROOT), "--json")
            print(f"  {OK} 建档 {sp['name']}（cron {sp['cron']} {sp['timezone']}, mode {sp['mode']}）")
            changed += 1
            continue
        sid = cur["id"]
        fixes = []
        if live_mode(sid) != sp["mode"]:
            paseo("schedule", "update", sid, "--mode", sp["mode"])
            fixes.append(f"mode→{sp['mode']}")
        if cur.get("cadence") != f"cron:{sp['cron']} ({sp['timezone']})":
            paseo("schedule", "update", sid, "--cron", sp["cron"], "--timezone", sp["timezone"])
            fixes.append(f"cron→{sp['cron']} {sp['timezone']}")
        if fixes:
            print(f"  {OK} 修正 {sp['name']} [{sid}]：{'，'.join(fixes)}")
            changed += 1
        else:
            print(f"  {OK} {sp['name']} [{sid}] 已符合，跳过")
    print(f"对账完成：{changed} 处变更。现网 id 查 `paseo schedule ls`。")
    return 0


def cmd_ls():
    for name, s in live_list().items():
        print(f"  {s['id']}  {name}  {s['cadence']}  {s['status']}")
    return 0


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    try:
        return {"check": cmd_check, "apply": cmd_apply, "ls": cmd_ls}[cmd]()
    except KeyError:
        sys.exit(f"未知子命令：{cmd}（用 check|apply|ls）")
    except (RuntimeError, FileNotFoundError) as e:
        sys.exit(f"error: {e}")


if __name__ == "__main__":
    sys.exit(main())
