#!/usr/bin/env bash
# papergirl · 控制台（paseo session，手机/终端远程运营公众号）。
# 一个常驻 agent 干全套：喂数据 / 查状态 / 看复盘 / 触发补跑。
# 手机端：装 Paseo App，`paseo onboard` 出二维码扫码配对，之后在 App 里直接和这个
# agent 对话即可（Mac 须醒着 + daemon 在跑）。终端用法见下。
#
#   bin/console.sh "讲 prompt injection 那篇 阅读35 在看2 转发3 涨粉1"   # 喂数据
#   bin/console.sh "今天跑了吗"                                          # 查状态
#   bin/console.sh "这周哪篇在看率最高"                                  # 看复盘
#   bin/console.sh "补跑 am"                                             # 触发补跑
#   bin/console.sh --image ~/Desktop/wx.png "喂这个"                     # 截图喂数据
#   bin/console.sh status                                               # 看 agent 最近输出
set -uo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
ID_FILE="$REPO/state/.console-agent-id"
# paseo CLI 是 /opt/homebrew/bin 下指向 Paseo.app 自带 bin/paseo 的 symlink，不依赖特定 node 版本
export PATH="$HOME/.local/bin:/usr/local/bin:/opt/homebrew/bin:$PATH"

PROMPT='你是 papergirl 项目的「控制台」助手，工作目录就是本项目根。我可能从手机（Paseo App）或终端找你，用来远程运营这个 AI 内容公众号。按我说的话判断意图，拿不准先问一句、别瞎操作。能干这四类：

【1. 喂效果数据】我给你公众号后台的数字（文字如「am 阅读234 在看12 转发5 涨粉3」，或后台截图）。
- 读 state/published.json（已发文章 + date/slot/title）和 state/metrics.json（已喂过的），找还没喂数据的文章。
- 数字对应到文章：截图按标题匹配；文字说 am/pm 对最近那档；没说日期默认最近一篇缺数据的。拿不准先问。
- 每篇跑：python3 tools/metrics.py add --date <YYYY-MM-DD> --slot <am|pm|walk> --read <阅读> --look <在看> --share <转发> --like <赞> --follow <涨粉>（缺的留空，别填0除非真是0）。映射：阅读→read 在看→look 转发→share 赞→like 涨粉→follow。
- 跑完一句话回我记了哪篇哪些数。

【2. 查状态】「今天跑了吗」「草稿箱有啥」「最近发了啥」。
- 读 state/runs/ 下今天日期的 *.json（status/title/media_id）和 state/published.json（最近几条）回我。简短，别贴大段原文。

【3. 看复盘】「这周哪篇最好」「数据怎样」。
- 跑 python3 tools/review.py，把在看率/阅读排行的要点总结成两三句回我。

【4. 触发补跑】「补跑 am」「补跑 pm」。这是 20-40 分钟的长任务，绝不要前台等。
- 先确认没有正在跑的：ps -ax | grep episode-runner（在跑就告诉我别重复起）。
- 没在跑就后台拉起、立刻返回：nohup bin/episode-runner.sh --slot <am|pm> >/dev/null 2>&1 &
- 回我「已在后台补跑 <am/pm>，20-40 分钟后完成会飞书通知」。

现在什么都不用做，只回「控制台就绪」。'

id_alive() { local id="$1"; [ -z "$id" ] && return 1; paseo inspect "$id" >/dev/null 2>&1; }

ID=""
[ -f "$ID_FILE" ] && ID="$(cat "$ID_FILE" 2>/dev/null)"
if ! id_alive "$ID"; then
  echo "[console] 没有可用的控制台 agent，新建 ..." >&2
  ID="$(paseo run --detach --title "papergirl 控制台" --cwd "$REPO" --provider claude --mode bypassPermissions "$PROMPT" --json 2>/dev/null \
        | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('agentId') or d.get('id') or '')")"
  [ -z "$ID" ] && { echo "[console] 创建失败" >&2; exit 1; }
  printf '%s\n' "$ID" > "$ID_FILE"
  paseo wait "$ID" --wait-timeout 60s >/dev/null 2>&1 || true
  echo "[console] 已就绪 id=$ID" >&2
fi

if [ "${1:-}" = "status" ]; then
  echo "控制台 agent id=$ID"
  paseo logs "$ID" 2>&1 | tail -8
  exit 0
fi

[ $# -eq 0 ] && { echo "用法：bin/console.sh \"<一句话指令>\"  或  bin/console.sh --image <图> \"喂这个\"" >&2; exit 2; }

paseo send "$ID" "$@"
