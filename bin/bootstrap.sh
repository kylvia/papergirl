#!/usr/bin/env bash
# papergirl · 一键重建（新机 / 迁移 / 灾后）。幂等：可反复跑，已就绪的跳过。
# 迁移不再是"照 CLAUDE.md 重做 N 步"——是跑这一条。今晚（2026-06-12）那次手工
# 重建（装 bun / symlink paseo / 重建 3 个 schedule / 重建控制台 agent）就是它要焊死的痛点。
#
# 前提：已装 Paseo 桌面版（提供 daemon）+ claude CLI + python3；.env 已填好凭证。
set -uo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"; cd "$REPO"
. "$REPO/bin/_env.sh"
G=$'\033[32m'; R=$'\033[31m'; N=$'\033[0m'
say() { printf "${G}%s${N}\n" "$1"; }
die() { printf "${R}✗ %s${N}\n" "$1" >&2; exit 1; }

say "== 1/5 运行时依赖 =="
# claude / python3：主体依赖，无法自动装
command -v claude  >/dev/null 2>&1 || die "缺 claude CLI，先装 Claude Code"
command -v python3 >/dev/null 2>&1 || die "缺 python3"
# bun：微信草稿 SDK 需要
if command -v bun >/dev/null 2>&1; then echo "  bun 已在"; else echo "  装 bun ..."; brew install oven-sh/bun/bun || die "bun 安装失败"; fi
# paseo CLI：随 Paseo.app 走，symlink 进 PATH（坑：npm 上同名 paseo 是无关 Next.js 包，别装）
if command -v paseo >/dev/null 2>&1; then echo "  paseo 已在"; else
  app="/Applications/Paseo.app/Contents/Resources/bin/paseo"
  [ -x "$app" ] || die "没找到 Paseo.app 自带 paseo，请先装 Paseo 桌面版"
  ln -sf "$app" /opt/homebrew/bin/paseo && echo "  paseo → symlink 到 /opt/homebrew/bin"
fi
# pyyaml：schedules.py 解析声明用
python3 -c 'import yaml' 2>/dev/null || { echo "  装 pyyaml ..."; python3 -m pip install --quiet pyyaml || die "pyyaml 安装失败"; }

say "== 2/5 凭证 =="
[ -f .env ] || die "缺 .env：cp .env.example .env，填公众号凭证+生图网关后再来"
chmod 600 .env && echo "  .env ok（已确保 0600）"

say "== 3/5 daemon 在线 =="
paseo schedule ls >/dev/null 2>&1 || die "paseo daemon 不可达：开着 Paseo 桌面版，或跑 paseo start"
echo "  daemon ok"

say "== 4/5 定时档对账（schedules.yaml → paseo）=="
python3 tools/schedules.py apply || die "schedule 对账失败"

say "== 5/5 控制台 agent =="
bin/console.sh status >/dev/null 2>&1 && echo "  控制台 agent 就绪" || echo "  （控制台 agent 重建跳过，手机/终端运营时 bin/console.sh 会自建）"

echo
say "重建完成，跑体检确认 ——"
exec bin/doctor.sh
