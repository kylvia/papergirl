#!/usr/bin/env bash
# papergirl · 一屏状态（接手先跑这个，只读不改）。
# 今天跑了吗 / 草稿箱待审 / 下次几点 / 该喂哪篇 / X 通不通——免得每次手敲 parse。
set -uo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"; cd "$REPO"
# 与 episode-runner 一致：nvm 最新 node 盖过 /usr/local/bin（node -v 才反映 episode 实际用的）
NVM_NODE_BIN="$(ls -d "$HOME"/.nvm/versions/node/v*/bin 2>/dev/null | sort -V | tail -1)"
export PATH="$HOME/.local/bin:${NVM_NODE_BIN:+$NVM_NODE_BIN:}/opt/homebrew/bin:/usr/local/bin:$PATH"
exec python3 tools/status.py
