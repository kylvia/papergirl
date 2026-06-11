#!/usr/bin/env bash
# papergirl episode runner：渲染任务书 → spawn 一个 claude 会话跑完
# 选题→深研→写稿→配图→推草稿箱 → 落 session_id 与运行记录。
# 不满意结果时：claude --resume <session_id> 继续改（runner 结束时会打印）。
set -uo pipefail

SLOT="am"; DATE="$(date +%F)"; DRY_RUN=0; PRINT_PROMPT=0
TIMEOUT_SECS="${EPISODE_TIMEOUT_SECS:-2400}"
while [ $# -gt 0 ]; do
  case "$1" in
    --slot)         SLOT="${2:-am}"; shift 2 ;;
    --date)         DATE="${2:-}"; shift 2 ;;
    --dry-run)      DRY_RUN=1; shift ;;
    --print-prompt) PRINT_PROMPT=1; shift ;;
    --timeout)      TIMEOUT_SECS="${2:-2400}"; shift 2 ;;
    *) echo "[episode] unknown arg: $1" >&2; exit 2 ;;
  esac
done

REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"
# ~/.local/bin 优先于 homebrew：uv 管理的 python3.13/3.14 自带完好 expat，
# 而 brew 的 python@3.14 bottle 在本机 pyexpat 符号缺失（last30days Reddit RSS 会降级）
export PATH="$HOME/.local/bin:/usr/local/bin:/opt/homebrew/bin:$HOME/.bun/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
CLAUDE_BIN="${CLAUDE_BIN:-claude}"

# X 源 cookie（可选）：tools/x_cookies.py 生成后在此 source，喂给 last30days
[ -f state/x-cookies.env ] && { set -a; . state/x-cookies.env; set +a; }

RUN_DIR="state/runs"; mkdir -p "$RUN_DIR" drafts
LOG="$RUN_DIR/$DATE-$SLOT.jsonl"
RECORD="$RUN_DIR/$DATE-$SLOT.json"

PROMPT="$(python3 - prompts/episode.md "$DATE" "$SLOT" <<'PY'
import sys
tmpl = open(sys.argv[1], encoding="utf-8").read()
sys.stdout.write(tmpl.replace("{DATE}", sys.argv[2]).replace("{SLOT}", sys.argv[3]))
PY
)"

if [ "$DRY_RUN" = "1" ]; then
  PROMPT="**🚧 DRY-RUN（本次必须遵守）**：全流程照常跑，但第 6 步推送必须带 \`--dry-run\`（只本地渲染，不调微信 API），最终 JSON 的 status 写 \"dry-run\"、media_id 留空。

---

$PROMPT"
  echo "[episode] DRY_RUN=1 — 不会真推草稿" >&2
fi

if [ "$PRINT_PROMPT" = "1" ]; then
  printf '%s\n' "$PROMPT"
  exit 0
fi

# 进程级超时（gtimeout/timeout 优先，缺则 perl alarm 兜底）
run_with_timeout() {
  local secs="$1"; shift
  local timeout_bin=""
  if command -v gtimeout >/dev/null 2>&1; then timeout_bin="gtimeout"
  elif command -v timeout >/dev/null 2>&1; then timeout_bin="timeout"; fi
  if [ -n "$timeout_bin" ]; then
    "$timeout_bin" "$secs" "$@"
  else
    perl -e '
      my $secs = shift; my $pid = fork();
      if ($pid == 0) { exec @ARGV; exit 127; }
      local $SIG{ALRM} = sub { kill "KILL", $pid; waitpid($pid, 0); exit 124; };
      alarm $secs; waitpid($pid, 0);
      my $status = $?;
      my $signal = $status & 127;
      exit(128 + $signal) if $signal;
      exit($status >> 8);
    ' "$secs" "$@"
  fi
}

echo "[episode] $DATE slot=$SLOT timeout=${TIMEOUT_SECS}s log=$LOG" >&2
: > "$LOG"
run_with_timeout "$TIMEOUT_SECS" "$CLAUDE_BIN" \
  -p "$PROMPT" \
  --output-format stream-json --verbose \
  --dangerously-skip-permissions \
  >> "$LOG" 2>&1 < /dev/null
rc=$?

IFS=$'\t' read -r STATUS SESSION TITLE MEDIA <<EOF
$(python3 tools/claude_session.py record --log "$LOG" --out "$RECORD" --date "$DATE" --slot "$SLOT" --rc "$rc")
EOF

echo "[episode] rc=$rc status=$STATUS title=$TITLE media_id=$MEDIA"
echo "[episode] record: $RECORD"
if [ -n "$SESSION" ] && [ "$SESSION" != "-" ]; then
  echo "[episode] 继续修改: claude --resume $SESSION"
fi

case "$STATUS" in
  pushed|dry-run|skipped) exit 0 ;;
esac
[ "$rc" -ne 0 ] && exit "$rc"
exit 1
