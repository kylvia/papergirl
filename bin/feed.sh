#!/usr/bin/env bash
# papergirl · 喂效果数据（paseo session 方式，不用记 agent id）。
# agent id 存在 state/.feed-agent-id；不存在或 agent 已没了就自动重建。
#
# 用法：
#   bin/feed.sh "am 阅读234 在看12 转发5 涨粉3"          # 文字
#   bin/feed.sh "am 阅读234 在看12; pm 阅读180 在看8"    # 一次喂两篇
#   bin/feed.sh --image ~/Desktop/wx.png "把这些喂进去"  # 直接甩后台截图
#   bin/feed.sh status                                   # 看 agent 最近输出
set -uo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
ID_FILE="$REPO/state/.feed-agent-id"
export PATH="$HOME/.local/bin:/usr/local/bin:/opt/homebrew/bin:$HOME/.nvm/versions/node/v22.19.0/bin:$PATH"

PROMPT='你是 papergirl 项目的「喂数据」助手，工作目录就是本项目根。
我会不定期把公众号后台的效果数据发给你——可能是文字（如「am 阅读234 在看12 转发5 涨粉3」），也可能直接是后台截图。
你的活：
1. 读 state/published.json（已发文章 + date/slot/title）和 state/metrics.json（已喂过的），找出还没喂数据的文章。
2. 把我给的数字对应到具体文章：截图按标题匹配；文字里我说 am/pm 就对最近那一档，没说日期默认最近一篇缺数据的。拿不准先问我，别瞎填。
3. 每篇跑：python3 tools/metrics.py add --date <YYYY-MM-DD> --slot <am|pm> --read <阅读> --look <在看> --share <转发/分享> --like <赞> --follow <涨粉>（缺的数留空别填0除非真是0）。映射：阅读→read 在看→look 转发/分享→share 点赞→like 涨粉→follow。
4. 跑完一句话回我：记了哪篇、哪些数。
现在什么都不用做，只回「就绪」。'

# 校验 id 文件里的 agent 还存在（paseo ls 默认只列最近几个，detached 的不在里面，
# 所以用 inspect 的退出码判存活，不用 ls）
id_alive() {
  local id="$1"; [ -z "$id" ] && return 1
  paseo inspect "$id" >/dev/null 2>&1
}

ID=""
[ -f "$ID_FILE" ] && ID="$(cat "$ID_FILE" 2>/dev/null)"
if ! id_alive "$ID"; then
  echo "[feed] 没有可用的喂数据 agent，新建 ..." >&2
  ID="$(paseo run --detach --title "papergirl 喂数据" --cwd "$REPO" --provider claude --mode bypassPermissions "$PROMPT" --json 2>/dev/null \
        | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('agentId') or d.get('id') or '')")"
  [ -z "$ID" ] && { echo "[feed] 创建失败" >&2; exit 1; }
  printf '%s\n' "$ID" > "$ID_FILE"
  paseo wait "$ID" --wait-timeout 60s >/dev/null 2>&1 || true
  echo "[feed] 已就绪 id=$ID" >&2
fi

if [ "${1:-}" = "status" ]; then
  echo "喂数据 agent id=$ID"
  paseo logs "$ID" 2>&1 | tail -8
  exit 0
fi

[ $# -eq 0 ] && { echo "用法：bin/feed.sh \"am 阅读234 在看12 转发5 涨粉3\"  或  bin/feed.sh --image <图> \"喂这些\"" >&2; exit 2; }

paseo send "$ID" "$@"
