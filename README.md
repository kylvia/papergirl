# papergirl 📮

单人 AI 内容公众号的全自动日更引擎。每天到点，一个 agent 会话独立完成：

**全网扫描**（[last30days](https://github.com/mvanhorn/last30days-skill)：Reddit / HN / GitHub / X…）→ **自主选题**（留下可审计的决策记录）→ **深研**（带引用简报）→ **写稿**（去 AI 味 + 标题自评）→ **配图**（AI 生图）→ **推草稿箱**。

人只做两件事：维护 `beats.yaml`（账号定位与赛道），以及在草稿箱终审、点群发。对结果不满意时拿着运行记录里的 session_id 一句话改稿：

```bash
claude --resume <session_id>   # "标题太平了，换个钩子重推"
```

## 设计要点

- **Agent-first**：流程本体是一份任务书（`prompts/episode.md`），不是状态机代码。调流程 = 改 prompt。
- **单会话跑到底**：没有阶段交接，selection 上下文天然留在会话里，resume 改稿不丢背景。
- **质量门是人**：自动化止步草稿箱，群发永远人工。
- **可插拔发布**：推稿走 `PUBLISHER` 适配器——`vault`(零凭证导出 md) 或 `wechat`(公众号草稿箱)，也能自己加 Substack/Ghost 等（见 `tools/publishers/`）。

## 5 分钟零凭证试跑（无需任何账号）

刚 fork 完，先跑一条命令看你处在哪条路、并立刻看到产出：

```bash
bin/onboard.sh   # 分清三条路依赖 + 直接跑一遍零凭证 vault 样例
```

或手动——用仓里自带的样例稿，走 `vault` 适配器看产出长什么样：

```bash
# 依赖：python3（这一步连 bun / 微信 / 生图网关都不需要）
PUBLISHER=vault python3 tools/push.py examples/2026-01-01-sample/draft.md \
  --title "AI 把这个函数写得很漂亮，只有一个问题——它是错的" \
  --cover examples/2026-01-01-sample/cover.png

# → drafts/vault/ 下生成自包含 bundle：note.md（带 frontmatter）+ assets/（封面与配图）
```

`examples/2026-01-01-sample/` 里还有一期 episode 的全套过程记录（decision / brief / gates），
clone 后不用先跑全流程就能看清结构与文风。详见 [`examples/README.md`](examples/README.md)。

## 真跑一期（需要 Claude Code）

完整日更由 `claude` agent 会话执行，所以这一步需要**已登录的 Claude Code CLI**；配图需要生图网关。

```bash
# 0. 依赖：claude (Claude Code CLI，已登录) / python3 / 生图网关；推 wechat 还需 bun
# 1. 配置
cp .env.example .env && $EDITOR .env    # 至少填 IMAGE_API_*（生图）；PUBLISHER 默认 wechat
chmod 600 .env

# 2. 验证（不调外部 API）
python3 tools/cover.py --title "测试" --out /tmp/c.png --dry-run
PUBLISHER=vault python3 tools/push.py examples/2026-01-01-sample/draft.md --title 测试   # 零凭证

# 3. 全流程演练 / 只看任务书
bin/episode-runner.sh --slot am --print-prompt     # 纯渲染任务书，零配置
bin/episode-runner.sh --slot am --dry-run          # 跑全流程但不真推（需 claude + 生图）

# 4. 真跑一期
bin/episode-runner.sh --slot am

# 5. 挂日更（paseo 或任意 cron，见 CLAUDE.md）
```

## 上线公众号（wechat 适配器）

想真推到微信公众号草稿箱，设 `PUBLISHER=wechat`（默认）并补公众号凭证：

```bash
# .env 里填：
WECHAT_APP_ID=...        # 公众号 → 开发 → 基本配置
WECHAT_APP_SECRET=...
WECHAT_PROXY_URL=...      # 微信 API 出站代理；该 IP 须在公众号白名单。本机 IP 已加白可留空
# 依赖 bun（首次自动 bun install vendored SDK）。只进草稿箱，群发永远人工。
```

要不要代理、以及怎么起一台（tinyproxy / Caddy 现成配置 + 白名单清单 + 验证）见 [`docs/proxy.md`](docs/proxy.md)。

## 环境变量

| 变量 | 用于 | 说明 |
|---|---|---|
| `PUBLISHER` | 推稿 | `wechat`(默认) \| `vault`(零凭证)；见 `tools/publishers/` |
| `IMAGE_API_URL` / `IMAGE_API_KEY` / `IMAGE_MODEL` | 配图 | 生图网关（OpenAI-compatible chat/completions） |
| `WECHAT_APP_ID` / `WECHAT_APP_SECRET` | wechat | 公众号凭证（vault 路径不需要） |
| `WECHAT_PROXY_URL` | wechat | 微信 API 出站代理；IP 须在公众号白名单 |
| `PAPERGIRL_VAULT_DIR` | vault | 导出目录，默认 `drafts/vault/` |
| `SCRAPECREATORS_API_KEY` 等 | 扫描 | last30days 可选增强源，见其 SKILL.md（不填也能跑：Reddit/HN/GitHub 免费） |

## 致谢与许可

本体 Apache-2.0（见 `LICENSE` / `NOTICE`）。bundled 三方各依其许可：

- 研究引擎：[mvanhorn/last30days-skill](https://github.com/mvanhorn/last30days-skill)（MIT，vendored at `.claude/skills/last30days/`）
- 微信草稿 SDK：origin [JimLiu/baoyu-skills](https://github.com/JimLiu/baoyu-skills)（vendored at `vendor/wechat-api/`，上游无显式 license，善意署名，见其 LICENSE.md）
