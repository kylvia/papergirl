# papergirl · 统一运行环境 —— 被 source，不要直接执行。
#
# 把"PATH 该怎么排"收成唯一真相，别再复制进每个脚本（runner/doctor/status/bootstrap/console
# 各抄一份正是引发 X 源 v16/v23 bug 的 PATH 漂移那类债）。三条硬约束：
#   ① ~/.local/bin 最前：uv 管的 python 自带完好 expat；brew 的 python@3.14 bottle 本机 pyexpat
#      符号缺失，排前面会让 last30days 的 Reddit RSS 降级。
#   ② nvm 最新 node 排在 /usr/local/bin 之前：否则 node 解析到 /usr/local/bin/node（本机 v16，
#      太老跑不了 bird-search 的 `import ... with {type:'json'}`），X 源会静默返 0。
#   ③ /opt/homebrew 提供 paseo/bun/brew；claude 在 nvm bin；python3 落 /usr/local（3.12，expat 完好）。
#
# node/python 都不在 nvm bin 之外被它抢走：nvm bin 只有 node/npm/npx/claude，python3 仍解析到 /usr/local。

_nvm_node_bin="$(ls -d "$HOME"/.nvm/versions/node/v*/bin 2>/dev/null | sort -V | tail -1)"
export PATH="$HOME/.local/bin:${_nvm_node_bin:+$_nvm_node_bin:}/usr/local/bin:/opt/homebrew/bin:$HOME/.bun/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
unset _nvm_node_bin
