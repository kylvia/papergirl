#!/usr/bin/env bash
# sync-public.sh — 把私有运行仓的代码同步到公开模板仓，自动脱敏后推送。
#
# 为什么需要：私有仓(papergirl-ops)是运行实例，含真实 state 与真实品牌名；
# 公开仓(papergirl)是干净模板。两仓历史不同，不能直接 push/merge，所以走
# 「git archive 抽 tracked tree → 脱敏 → 在公开历史上 commit → push」。
#
# 安全保证：
#   - 只同步 git tracked 文件（gitignored 的 drafts/runs/metrics/.env/缓存天然排除）
#   - state/published.json 不同步（公开仓自己保持 []，dedup 从零起）
#   - 脱敏后过安全门：仍检出品牌名/内部名则中止，绝不推送
#
# 用法：
#   bin/sync-public.sh ["commit message"]
#   PUBLIC_REMOTE=git@github.com:you/your-public.git bin/sync-public.sh
set -euo pipefail

PUBLIC_REMOTE="${PUBLIC_REMOTE:-git@github.com:kylvia/papergirl.git}"
PRIVATE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MSG="${1:-sync: 从私有运行仓同步代码（自动脱敏）}"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/papergirl-public.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT

# 公开仓自管、不接收私有 state 的 tracked 文件（正则，逐行匹配 ls-files 输出）
EXCLUDE='^state/published\.json$'

echo "[sync] 私有仓: $PRIVATE"
echo "[sync] 公开仓: $PUBLIC_REMOTE"
if ! git -C "$PRIVATE" diff --quiet || ! git -C "$PRIVATE" diff --cached --quiet; then
  echo "[sync] ⚠️ 私有仓有未提交改动；同步的是 HEAD（已提交）的快照，请先 commit 想发布的改动"
fi

echo "[sync] clone 公开仓 → $WORK"
git clone -q "$PUBLIC_REMOTE" "$WORK"

echo "[sync] 抽私有仓 HEAD 的 tracked tree 覆盖到公开 clone（排除私有 state）"
git -C "$PRIVATE" archive HEAD | tar --exclude='state/published.json' -xf - -C "$WORK"

echo "[sync] 处理删除（公开有、私有 HEAD 已无的 tracked 文件）"
comm -23 \
  <(git -C "$WORK" ls-files | sort) \
  <( { git -C "$PRIVATE" ls-tree -r --name-only HEAD | grep -vE "$EXCLUDE"; echo 'state/published.json'; } | sort ) \
  | while IFS= read -r f; do
      [ -n "$f" ] && git -C "$WORK" rm -q --ignore-unmatch -- "$f" >/dev/null || true
    done

echo "[sync] 脱敏（品牌名/内部名 → 公开占位；已清的留作安全网）"
python3 - "$WORK" <<'PY'
import os, sys
work = sys.argv[1]
# (old, new)，顺序敏感：长串/具体在前，裸词兜底在后
pairs = [
    ("扫码关注本公众号", "扫码关注本公众号"),
    ("本公众号", "本公众号"),
    ("JimLiu/baoyu-skills", "JimLiu/baoyu-skills"),
    (".papergirl", ".papergirl"),
    ("wechat-post", "wechat-post"),
    ("configEnv", "configEnv"),
    ("baoyu-skills", "baoyu-skills"),
    ("papergirl", "papergirl"),
]
for root, dirs, files in os.walk(work):
    if ".git" in dirs:
        dirs.remove(".git")
    for fn in files:
        p = os.path.join(root, fn)
        try:
            with open(p, "r", encoding="utf-8") as f:
                t = f.read()
        except (UnicodeDecodeError, IsADirectoryError, PermissionError):
            continue
        n = t
        for a, b in pairs:
            n = n.replace(a, b)
        if n != t:
            with open(p, "w", encoding="utf-8") as f:
                f.write(n)
PY

cd "$WORK"
git add -A

echo "[sync] 安全门：确认公开 clone 无品牌名/内部名"
if git grep -nE '本公众号|baoyu-skills|papergirl' -- . >/dev/null 2>&1; then
  echo "[sync] ❌ 脱敏后仍检出敏感词，已中止（不推送）。命中："
  git grep -nE '本公众号|baoyu-skills|papergirl' -- . | head
  exit 1
fi

if git diff --cached --quiet; then
  echo "[sync] ✅ 公开仓已是最新，无改动，无需推送。"
  exit 0
fi

echo "[sync] 改动："
git --no-pager diff --cached --stat | tail -25
git -c user.name='papergirl' -c user.email='noreply@papergirl' commit -q -m "$MSG"
git push -q origin HEAD:main
echo "[sync] ✅ 已推送到 $PUBLIC_REMOTE"
