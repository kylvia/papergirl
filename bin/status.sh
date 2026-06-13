#!/usr/bin/env bash
# papergirl · 一屏状态（接手先跑这个，只读不改）。
# 今天跑了吗 / 草稿箱待审 / 下次几点 / 该喂哪篇 / X 通不通——免得每次手敲 parse。
set -uo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"; cd "$REPO"
. "$REPO/bin/_env.sh"
exec python3 tools/status.py
