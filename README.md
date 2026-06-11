# papergirl 📮

单人 AI 内容公众号的全自动日更引擎。每天到点，一个 agent 会话独立完成：

**全网扫描**（[last30days](https://github.com/mvanhorn/last30days-skill)：Reddit / HN / GitHub / X…）→ **自主选题**（留下可审计的决策记录）→ **深研**（带引用简报）→ **写稿**（去 AI 味 + 标题自评）→ **配图**（AI 生图）→ **推公众号草稿箱**。

人只做两件事：维护 `beats.yaml`（账号定位与赛道），以及在草稿箱终审、点群发。对结果不满意时拿着运行记录里的 session_id 一句话改稿：

```bash
claude --resume <session_id>   # "标题太平了，换个钩子重推"
```

## 设计要点

- **Agent-first**：流程本体是一份任务书（`prompts/episode.md`），不是状态机代码。调流程 = 改 prompt。
- **单会话跑到底**：没有阶段交接，selection 上下文天然留在会话里，resume 改稿不丢背景。
- **质量门是人**：自动化止步草稿箱，群发永远人工。
- **决策可审计**：每期的候选清单、评分、弃选理由都写盘（`state/runs/`）。

## Quickstart

```bash
# 0. 依赖：claude (Claude Code CLI) / bun / python3
# 1. 配置
cp .env.example .env && $EDITOR .env   # 公众号凭证 + 生图网关 + 可选微信代理
chmod 600 .env

# 2. 验证两条腿
python3 tools/cover.py --title "测试" --out /tmp/c.png --dry-run
python3 tools/push.py README.md --dry-run

# 3. 全流程演练（不真推）
bin/episode-runner.sh --slot am --dry-run

# 4. 真跑一期
bin/episode-runner.sh --slot am

# 5. 挂日更（paseo 或任意 cron，见 CLAUDE.md）
```

## 环境变量

| 变量 | 说明 |
|---|---|
| `WECHAT_APP_ID` / `WECHAT_APP_SECRET` | 公众号凭证（开发 → 基本配置） |
| `WECHAT_PROXY_URL` | 微信 API 出站代理；该 IP 须在公众号白名单。本机 IP 已加白可留空 |
| `IMAGE_API_URL` / `IMAGE_API_KEY` / `IMAGE_MODEL` | 生图网关（OpenAI-compatible chat/completions） |
| `SCRAPECREATORS_API_KEY` 等 | last30days 可选增强源，见其 SKILL.md |

## 致谢与许可

- 研究引擎：[mvanhorn/last30days-skill](https://github.com/mvanhorn/last30days-skill)（MIT，vendored at `.claude/skills/last30days/`）
- 微信草稿 SDK：origin [JimLiu/baoyu-skills](https://github.com/JimLiu/baoyu-skills)（vendored at `vendor/wechat-api/`，见 LICENSE.md）
