#!/usr/bin/env bash
# papergirl · 体检 —— 把"坑"变成会自己报警的守卫。
# 绿=这条经验已编码且在守着；红=硬故障，多数 bin/bootstrap.sh 能修；黄=可选项/降级，不阻断。
# 取代 CLAUDE.md 里一堆"(日期 踩过)"的口述坑：能查的现查，能验的现验，别再靠人记。
set -uo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"; cd "$REPO"
XPROBE=0; [ "${1:-}" = "--x" ] && XPROBE=1   # --x：额外真拉一次 X，验证实际通不通（慢、走网络）
# 与 episode-runner 一致：nvm 最新 node 盖过 /usr/local/bin 的老 node（v16，X 源需要 ≥18）
NVM_NODE_BIN="$(ls -d "$HOME"/.nvm/versions/node/v*/bin 2>/dev/null | sort -V | tail -1)"
export PATH="$HOME/.local/bin:${NVM_NODE_BIN:+$NVM_NODE_BIN:}/opt/homebrew/bin:/usr/local/bin:$PATH"

G=$'\033[32m'; Y=$'\033[33m'; R=$'\033[31m'; N=$'\033[0m'
fails=0
ok()   { printf "  ${G}✓${N} %s\n" "$1"; }
warn() { printf "  ${Y}⚠${N} %s\n" "$1"; }
bad()  { printf "  ${R}✗${N} %s\n" "$1"; fails=$((fails+1)); }

echo "== 运行时依赖 =="
for c in claude bun python3 paseo; do
  if command -v "$c" >/dev/null 2>&1; then ok "$c → $(command -v "$c")"; else bad "$c 缺失（跑 bin/bootstrap.sh）"; fi
done
# node 单列查版本：bird-search 用 import attributes，老 node（本机 /usr/local/bin 是 v16）跑不了 → X 源静默返 0
if command -v node >/dev/null 2>&1; then
  nm=$(node -v | sed -E 's/^v([0-9]+).*/\1/')
  if [ "$nm" -ge 18 ] 2>/dev/null; then ok "node $(node -v) @ $(command -v node)（≥18，X 源可用）"
  else bad "node $(node -v) 过低（<18），X 源会静默返 0——确认 episode-runner 锁了 nvm 最新 node"; fi
else bad "node 缺失"; fi

echo "== 凭证 =="
if [ -f .env ]; then
  perm=$(stat -f '%Lp' .env 2>/dev/null || echo '?')
  [ "$perm" = "600" ] && ok ".env 存在且 0600" || warn ".env 权限 $perm（应 600：chmod 600 .env）"
else bad ".env 缺失（cp .env.example .env 后填凭证）"; fi

echo "== 定时档（对账 schedules.yaml）=="
if ! python3 tools/schedules.py check; then fails=$((fails+1)); fi

echo "== 控制台 agent =="
cid=$(cat state/.console-agent-id 2>/dev/null || true)
if [ -n "$cid" ] && paseo inspect "$cid" >/dev/null 2>&1; then ok "活着 [$cid]"
else warn "不在（bin/console.sh status 会自动重建，手机/终端运营才需要）"; fi

echo "== 两条腿（dry-run）=="
if python3 tools/cover.py --title 体检 --out /tmp/papergirl-doctor.png --dry-run >/dev/null 2>&1; then ok "生图 cover.py"; else bad "cover.py dry-run 失败"; fi
if python3 tools/push.py README.md --dry-run >/dev/null 2>&1; then ok "推送 push.py（微信 SDK 链路）"; else bad "push.py dry-run 失败"; fi

echo "== X 源（可选增强）=="
if [ -f state/x-cookies.env ]; then
  ok "x-cookies.env 在（失效就重跑 tools/x_cookies.py）"
  if [ "$XPROBE" = "1" ]; then
    ( set -a; . state/x-cookies.env; set +a
      n=$(cd .claude/skills/last30days/scripts && python3 -c "import sys;sys.path.insert(0,'.')
from lib.bird_x import search_x
r=search_x('AI','2026-06-10','2026-06-13',depth='quick')
i=r.get('items') if isinstance(r,dict) else r
print(len(i) if hasattr(i,'__len__') else 0)" 2>/dev/null)
      if [ -n "$n" ] && [ "$n" -gt 0 ] 2>/dev/null; then ok "X 实拉验证：返回 $n 条推文"; else warn "X 实拉返回 0（cookie 可能失效，重跑 tools/x_cookies.py）"; fi )
  else
    echo "    （加 bin/doctor.sh --x 可真拉一次验证 X 实际通不通）"
  fi
else warn "无 x-cookies.env：X 源降级跳过，不影响日更（python3 tools/x_cookies.py 启用）"; fi

echo
if [ "$fails" -eq 0 ]; then
  printf "${G}体检通过${N}（⚠ 为可选项，不阻断日更）\n"; exit 0
else
  printf "${R}体检发现 %s 处硬故障${N} —— 先跑 bin/bootstrap.sh，仍红再查具体项\n" "$fails"; exit 1
fi
