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
. "$REPO/bin/_env.sh"   # 统一 PATH（含 nvm 最新 node 盖过老 v16 —— X 源依赖；约束见 _env.sh）
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
# 超时把子进程放进**独立进程组**，到点杀整个组——否则只杀 claude 会把它的
# python 子进程（last30days/cover）甩成孤儿挂到 PID 1 继续跑。gtimeout/timeout 默认
# 只杀直接子进程，同样会留孤儿，所以统一走 perl 进程组方案（perl 在 macOS/Linux 都有）。
run_with_timeout() {
  local secs="$1"; shift
  perl -e '
    use POSIX qw(setpgid);
    my $secs = shift;
    my $pid = fork();
    if ($pid == 0) { setpgid(0, 0); exec @ARGV; exit 127; }
    setpgid($pid, $pid);  # 父子都设一次，规避竞态；任一成功即可
    local $SIG{ALRM} = sub { kill("KILL", -$pid); waitpid($pid, 0); exit 124; };
    alarm $secs;
    waitpid($pid, 0);
    my $status = $?;
    my $signal = $status & 127;
    exit(128 + $signal) if $signal;
    exit($status >> 8);
  ' "$secs" "$@"
}

echo "[episode] $DATE slot=$SLOT timeout=${TIMEOUT_SECS}s log=$LOG" >&2
: > "$LOG"

# ---- 抗瞬态网络 + 阶段 checkpoint ----
# episode 是单个 claude -p 会话；socket 一断整轮判死。这里不重扫，而是 --resume 同
# session 从盘上产物的断点续跑，只对**瞬态**错误自动重试，并用 published.json 防重复推。
MAX_RESUMES="${EPISODE_MAX_RESUMES:-3}"
RUN_PREFIX="$RUN_DIR/$DATE-$SLOT"

already_pushed() {  # published.json 有今天本档记录 = 已真推成功（防 resume 二次推）
  python3 - "$DATE" "$SLOT" <<'PY'
import json, sys
try:
    d = json.load(open("state/published.json"))
except Exception:
    sys.exit(1)
sys.exit(0 if any(e.get("date") == sys.argv[1] and e.get("slot") == sys.argv[2] for e in d) else 1)
PY
}

current_phase() {  # 从盘上产物推断最远完成阶段（固定名产物，episode.md 每步必写）
  already_pushed                   && { echo pushed;     return; }
  [ -f "$RUN_PREFIX-gates.md" ]    && { echo written;    return; }
  [ -f "$RUN_PREFIX-brief.md" ]    && { echo researched; return; }
  [ -f "$RUN_PREFIX-decision.md" ] && { echo picked;     return; }
  echo start
}

is_transient() {  # 值得自动 resume 的瞬态错误；区别于真·内容/逻辑失败
  tail -c 6000 "$LOG" 2>/dev/null | grep -qiE \
    'socket connection was closed|connection closed|ECONNRESET|ECONNREFUSED|ETIMEDOUT|EPIPE|Unable to connect to API|fetch failed|terminated unexpectedly|network error|503|overloaded|stream (error|disconnected)'
}

resume_prompt() {  # 续跑指令：从断点接着跑，绝不重做/重选题/重复推
  [ "$DRY_RUN" = "1" ] && printf '%s\n\n' '**🚧 DRY-RUN（本次必须遵守）**：第 6 步推送必须带 `--dry-run`，最终 JSON 的 status 写 "dry-run"、media_id 留空。'
  cat <<EOF
上一轮本会话因瞬态错误中断（多为 API 网络断流），现已恢复。盘上产物（state/runs/$DATE-$SLOT-*.md、drafts/）都有效，**别重做已完成步骤、别重新选题/重扫**。

先自查：若 state/published.json 已有 date=$DATE slot=$SLOT 的记录，说明已推成功，**直接输出第 7 步那行最终 JSON 收尾，不要再推**。否则从断点继续，依次走完到推草稿箱→更新 published.json→末行 JSON。检测到的最远完成阶段：$1。

硬规则照旧：全程前台同步、不后台化、不输出末行 JSON 前不结束本轮。DATE=$DATE SLOT=$SLOT。
EOF
}

STATUS=""; SESSION=""; TITLE=""; MEDIA=""; rc=1
attempt=0
while : ; do
  if [ "$attempt" -eq 0 ]; then
    run_with_timeout "$TIMEOUT_SECS" "$CLAUDE_BIN" \
      -p "$PROMPT" \
      --output-format stream-json --verbose \
      --dangerously-skip-permissions \
      >> "$LOG" 2>&1 < /dev/null
    rc=$?
  else
    PH="$(current_phase)"
    echo "[episode] 瞬态失败，自动 resume（第 $attempt/$MAX_RESUMES 次，phase=$PH，session=$SESSION）" >&2
    run_with_timeout "$TIMEOUT_SECS" "$CLAUDE_BIN" \
      --resume "$SESSION" -p "$(resume_prompt "$PH")" \
      --output-format stream-json --verbose \
      --dangerously-skip-permissions \
      >> "$LOG" 2>&1 < /dev/null
    rc=$?
  fi

  # 复用 claude_session.py 解析当前状态（每次覆盖写 RECORD）
  STATUS=""; SESSION_NEW=""; TITLE=""; MEDIA=""
  IFS=$'\t' read -r STATUS SESSION_NEW TITLE MEDIA <<EOF
$(python3 tools/claude_session.py record --log "$LOG" --out "$RECORD" --date "$DATE" --slot "$SLOT" --rc "$rc")
EOF
  STATUS="${STATUS:-}"; TITLE="${TITLE:-}"; MEDIA="${MEDIA:-}"
  [ -n "$SESSION_NEW" ] && [ "$SESSION_NEW" != "-" ] && SESSION="$SESSION_NEW"

  case "$STATUS" in pushed|dry-run|skipped) break ;; esac   # 正常收尾
  already_pushed && { STATUS="pushed"; break; }              # 没出末行 JSON 但已真推 → 视为成功

  # 失败：瞬态 + 有额度 + 有 session 可续 → 退避后 resume；否则认账
  if [ "$attempt" -lt "$MAX_RESUMES" ] && [ -n "$SESSION" ] && [ "$SESSION" != "-" ] && is_transient; then
    attempt=$((attempt + 1))
    backoff=$((attempt * ${EPISODE_RESUME_BACKOFF:-30}))
    echo "[episode] 瞬态错误，${backoff}s 后第 $attempt 次 resume …" >&2
    sleep "$backoff"
    continue
  fi
  break
done

echo "[episode] rc=$rc status=${STATUS} title=${TITLE} media_id=${MEDIA}"
echo "[episode] record: $RECORD"
if [ -n "${SESSION}" ] && [ "${SESSION}" != "-" ]; then
  echo "[episode] 继续修改: claude --resume ${SESSION}"
fi

# 推送给人——让无人值守跑完能喊到你。未配 NOTIFY_WEBHOOK 时自动降级为本地打印。
case "${STATUS}" in
  pushed)  NOTE="📮 papergirl ${DATE}-${SLOT} 草稿就绪：《${TITLE}》。去公众号后台终审+群发。" ;;
  dry-run) NOTE="🧪 papergirl ${DATE}-${SLOT} dry-run 跑通：《${TITLE}》（未真推）。" ;;
  skipped) NOTE="🛑 papergirl ${DATE}-${SLOT} 跳过：素材不足未出稿。" ;;
  *)       NOTE="⚠️ papergirl ${DATE}-${SLOT} 失败（status=${STATUS} rc=${rc}）。看日志 ${LOG}" ;;
esac
python3 "$REPO/tools/notify.py" "${NOTE}" >/dev/null 2>&1 || true

case "${STATUS}" in
  pushed|dry-run|skipped) exit 0 ;;
esac
[ "$rc" -ne 0 ] && exit "$rc"
exit 1
