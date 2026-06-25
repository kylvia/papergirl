#!/usr/bin/env bash
# papergirl · onboard —— 给 fork 者的 5 分钟上手。
#
# 不假设你有微信账号 / 生图网关 / paseo。分清三条路各需什么，并直接帮你跑一遍
# 零凭证的 vault 样例，让你立刻看到产出。
# （运营者日常自检请用 bin/doctor.sh；新机/灾后重建用 bin/bootstrap.sh。）
set -uo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"; cd "$REPO"

G=$'\033[32m'; Y=$'\033[33m'; N=$'\033[0m'
ok()      { printf "  ${G}✓${N} %s\n" "$1"; }
miss()    { printf "  ${Y}—${N} %s\n" "$1"; }
has()     { command -v "$1" >/dev/null 2>&1; }
env_has() { [ -f .env ] && grep -qE "^$1=.+" .env; }

echo "papergirl · onboard —— 三条路，按需准备依赖；core 够了就能立刻看到产出。"
echo

echo "== ① core：vault 零凭证路径 =="
core_ok=1
if has python3; then ok "python3 → $(command -v python3)"
else miss "python3 缺——这条也跑不了，先装 python3"; core_ok=0; fi
echo "    够了就能：看清产出结构、把成稿导出成自包含 markdown bundle（无需任何账号/网关）"

echo "== ② 真跑一期：agent 全流程 =="
if has claude; then ok "claude → $(command -v claude)（确保已 \`claude login\`）"
else miss "claude 缺——完整日更由它执行：装 Claude Code CLI 并登录"; fi
if env_has IMAGE_API_URL && env_has IMAGE_API_KEY; then ok ".env 已配 IMAGE_API（生图网关）"
else miss "生图网关未配——封面步骤需要：cp .env.example .env，填 IMAGE_API_URL/KEY/MODEL"; fi

echo "== ③ 上线公众号：wechat 适配器（可选）=="
if has bun; then ok "bun → $(command -v bun)"; else miss "bun 缺——仅 wechat 推送需要"; fi
if env_has WECHAT_APP_ID && env_has WECHAT_APP_SECRET; then ok ".env 已配公众号凭证"
else miss "公众号凭证未配——仅 PUBLISHER=wechat 需要（vault 路径不需要）"; fi
echo

SAMPLE=examples/2026-01-01-sample
if [ "$core_ok" = 1 ] && [ -f "$SAMPLE/draft.md" ]; then
  echo "== 试跑：样例稿走 vault 适配器导出（零凭证，真跑）=="
  if out=$(PUBLISHER=vault python3 tools/push.py "$SAMPLE/draft.md" \
        --title "AI 把这个函数写得很漂亮，只有一个问题——它是错的" \
        --cover "$SAMPLE/cover.png" 2>&1); then
    note=$(printf '%s\n' "$out" | awk -F'\t' '/^vault\t/{print $2}')
    ok "导出成功 → ${note:-drafts/vault/...}"
    if [ -n "$note" ] && [ -d "$(dirname "$note")" ]; then
      echo "    bundle 内容："
      ( cd "$(dirname "$note")" && find . -type f | sed 's|^\./|      |' )
    fi
  else
    miss "试跑失败（不影响其它路径）："; printf '%s\n' "$out" | sed 's/^/      /'
  fi
  echo
fi

echo "== 你现在能做什么 =="
echo "  • 看产出结构：examples/2026-01-01-sample/（draft / decision / brief / gates + 封面）"
echo "  • 零凭证导出：PUBLISHER=vault python3 tools/push.py <你的稿.md> --title … --cover …"
echo "  • 真跑一期（需 claude 登录 + 生图）：bin/episode-runner.sh --slot am"
echo "  • 改方向：beats.yaml（赛道+信息源）、voice.md（文风）；流程本体 prompts/episode.md"
echo "  详见 README.md。运营者日常自检用 bin/doctor.sh。"
