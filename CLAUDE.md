# papergirl —— 项目宪法

> 单人 AI 内容公众号的全自动日更引擎：last30days 全网扫描 → agent 自主选题 →
> 写稿配图 → 推公众号草稿箱。人只做两件事：维护 `beats.yaml`、在草稿箱终审群发。
> Agent-first：流程主体是 prompt（`prompts/episode.md`），代码只是工具。

## 一次 episode 的真相

```
paseo（或手动）→ bin/episode-runner.sh --slot am
  └─ spawn 一个 claude 会话执行 prompts/episode.md：
     扫描(last30days) → 定题(写决策记录) → 深研(带引用简报)
     → 写稿(去AI味+标题自评) → 配图(tools/cover.py)
     → 推草稿箱(tools/push.py) → 更新 state/published.json → 末行 JSON
  └─ runner 落 state/runs/<date>-<slot>.json（含 session_id）
人工追加轮（可选）：claude --resume <session_id> "标题太平了，换个钩子重推"
```

- runner 结束会打印 resume 命令；session 里有完整选题理由和简报上下文
- 质量门 = 你本人：草稿箱终审 + resume 改稿，没有自动群发

## 目录职责

| 路径 | 职责 | 改动方式 |
|---|---|---|
| `beats.yaml` | 赛道与账号定位（目标函数） | 人直接改，零代码 |
| `voice.md` | 声音档（人设/视角/文章原型/范文库/四层闸门） | 调文风改这里，写稿阶段硬约束 |
| `prompts/episode.md` | episode 任务书（流程本体） | 调流程改这里，不是改代码 |
| `bin/episode-runner.sh` | spawn claude + 抓 session_id + 落运行记录 | 唯一 runner |
| `bin/bootstrap.sh` | 新机/迁移一键重建（依赖+schedule+控制台 agent），幂等 | 自有代码 |
| `bin/doctor.sh` | 体检：把"坑"变成会报警的守卫，绿=经验在守 | 自有代码 |
| `schedules.yaml` | 定时档声明源真相（不写死 id） | 人改这里，再 bootstrap 对齐 |
| `tools/schedules.py` | schedule 对账引擎（apply/check，bootstrap+doctor 共用） | 自有代码 |
| `tools/cover.py` | 生图（OpenAI-compatible 网关） | 自有代码 |
| `tools/push.py` | 推草稿（注入 per-process 微信代理） | 自有代码 |
| `tools/claude_session.py` | stream-json 解析 + 运行记录 | 自有代码 |
| `tools/metrics.py` | 效果数据回流（人工喂，个人订阅号无 API） | 自有代码 |
| `tools/review.py` | 每周复盘：质量信号归因到赛道/原型 | 自有代码 |
| `tools/notify.py` | 推送通知（lark/wecom/feishu…），无人值守喊到人 | 自有代码 |
| `tools/metrics_nudge.py` | 催数据：发布满 N 天没喂 metrics 就提醒 | 自有代码 |
| `bin/console.sh` | 远程控制台：常驻 paseo agent，手机/终端运营（喂数据/查状态/复盘/补跑） | 自有代码 |
| `vendor/wechat-api/` | 微信草稿 SDK（vendored，origin baoyu-skills） | 不改；见 UPSTREAM.md |
| `.claude/skills/last30days/` | 全网研究 skill（vendored，MIT） | 不改；见 UPSTREAM.md |
| `state/published.json` | 发文史，选题查重的事实源 | episode 自动追加 |
| `state/runs/` | 每期决策记录/简报/日志/session_id | episode 自动写，gitignored |
| `drafts/` | 文章与图片产物 | episode 自动写，gitignored |

## 硬规则（episode agent 与维护者都必须遵守）

1. **凭证只住 `.env`**（gitignored，0600）。任何凭证不进 git、不打印到日志。仓库开源前跑一遍泄漏扫描。
2. **微信代理是 per-process 的**：只由 `tools/push.py` 注入给推送子进程。绝不全局 export HTTPS_PROXY——生图和抓取走代理会被 filter 403。
3. **正文图片必须先落地本地**再引用：代理 filter 只放行微信域，外域图片 URL 推送时会 403。
4. **事实必须有出处**：论断锚到深研简报或核实过的来源，查不到就删，禁止编造数字/引语。
5. **只进草稿箱，不群发**。群发永远是人工在公众号后台完成。
6. 推送成功必须更新 `state/published.json`——这是防止重复选题的唯一事实源。
7. 推送必须走 `python3 tools/push.py`，不要裸跑 `bun vendor/wechat-api/wechat-api.ts`。

## 常用命令

```bash
# 新机/迁移/灾后一键重建（幂等）；日常体检
bin/bootstrap.sh
bin/doctor.sh

# 手动跑一期（全流程但不真推）
bin/episode-runner.sh --slot am --dry-run

# 手动跑一期（真推草稿箱）
bin/episode-runner.sh --slot am

# 只看渲染后的任务书
bin/episode-runner.sh --slot am --print-prompt

# 对某期结果继续修改（session_id 在 state/runs/<date>-<slot>.json）
claude --resume <session_id>

# 单测两条腿
python3 tools/cover.py --title "测试" --out /tmp/c.png --dry-run
python3 tools/push.py drafts/<x>.md --dry-run --verbose
```

## Paseo 双更接入

定时档的**声明源真相是 [`schedules.yaml`](schedules.yaml)**（am/pm/催数据三档：cron、mode、prompt 都在那）。
**不在这里手写 schedule id**——id 由 paseo 运行时分配、迁移即作废（这张表以前就是这么腐烂的，
2026-06-12 迁移新机被它坑过）。现网 id/状态现查 `paseo schedule ls`；改档改 `schedules.yaml` 后跑
`bin/bootstrap.sh`（或 `python3 tools/schedules.py apply`）让 paseo 对齐。

| 档 | 北京时 | 草稿就绪 | 建议群发窗口 |
|---|---|---|---|
| am | 07:30 | ~08:15 | 午间 12:00–13:00 |
| pm | 16:30 | ~17:15 | 晚间 20:00–21:30（最强开篇时段） |

pm 晚跑蹭当天最新 AI 新闻，靠 published.json 7 天去重自动避开 am 主题；催数据档北京 11:00。
paseo 任务只跑 runner 并汇报。

**运维入口（坑已变守卫，别再靠人记）**：
- 新机/迁移/灾后一键重建：`bin/bootstrap.sh`（幂等，装齐依赖+对齐 schedule+建控制台 agent）。
- 日常体检：`bin/doctor.sh`（绿=经验在守；红=硬故障）。原先一堆「(日期 踩过)」的口述坑——
  schedule 必须 bypassPermissions、paseo CLI 随 Paseo.app 走（npm 同名包是坑）、.env 须 0600——
  现在都编码进 `schedules.yaml`/`tools/schedules.py`/`bin/bootstrap.sh` 并由 doctor 守着，详见各自注释。

**仍要人脑记的两条**（编不进代码）：
- Mac 睡眠会错过定时点，paseo 唤醒后补跑（时间不精确但不丢）。要随时可用就别让 Mac 休眠。
- episode 偶遇 Anthropic API `socket closed`/`ECONNRESET` 会中途死（status=error，**非内容问题**）。
  session 完好、扫描/选题/简报已落盘——用 runner 打印的 `claude --resume <session_id>` 从写稿续，别重扫；
  网络在抽风时连 resume 也接着撞，等链路稳再续。

## 增长闭环（北极星=质量加权）

个人订阅号无微信数据 API（datacube/getarticletotal/freepublish 全 48001），所以数据靠人工喂。
北极星指标是**质量加权**：在看率 / 分享率 / 涨粉每篇，不看裸阅读数（防标题党腐蚀"事实严谨"定位）。

```bash
# 发布 1-3 天后，从后台读 4 个数贴回来（每篇 ~30 秒）
python3 tools/metrics.py add --date 2026-06-12 --slot am --read 1234 --look 56 --share 23 --follow 9
# 每周复盘：谁的在看率系统性偏高偏低 → 调整建议（不自动改，样本小先看）
python3 tools/review.py
```

闭环：episode 出稿（published.json 记 beat/archetype/字数/配图数/选题热度）→ 人群发 →
人喂 metrics → review.py 归因到赛道/原型 → 调 beats.yaml 权重 + voice.md 标题范式。

**冷启动告诫**：日更样本小，早期（<8 篇）只看单篇排行 + 人的口味判断，别自动调权重——会学到噪声。
real signal 要攒几周。review.py 刻意只报告+建议，不自动 mutate。

## 跨期趋势记忆（last30days store）

扫描时带 `--store`，证据沉淀进 `~/.local/share/last30days/research.db`（last30days 默认库）。
PICK 步骤用 `store.py trending --days 7` 拿跨天升温信号，把"上升期"判断从单次猜测变成累积数据。

```bash
python3 .claude/skills/last30days/scripts/store.py trending --days 7   # 升温主题
python3 .claude/skills/last30days/scripts/store.py stats               # 库概况
python3 .claude/skills/last30days/scripts/store.py query "<topic>" --since 7d
```

库随每期累积，越跑趋势判断越准。engine 与 store.py 共用同一默认库，无需配路径。
（未来可选：`watchlist.py` 追连续剧式选题、`briefing.py --weekly` 出周报——想要某种文章形态时再加。）

## X 源（可选增强）

last30days 的 X 源要 `auth_token`（httpOnly cookie）。`tools/x_cookies.py` 走 last30days
自带的原生提取（直接读浏览器 Cookies SQLite + macOS Keychain 解密，httpOnly 只挡页面 JS、
不挡磁盘读取），无需 browser-relay、不改任何全局包。

启用（人在场时跑一次，cookie 能撑数月）：

```bash
# 前置：macOS + 用 Chrome（或 Brave/Firefox/Safari）登录过 x.com
python3 tools/x_cookies.py          # 提取 auth_token+ct0 → state/x-cookies.env(0600)
python3 tools/x_cookies.py --check  # 只验证不写文件
```

之后 episode-runner 自动 source，X 信号并入 last30days。失效了重跑即可；episode 取不到也只是降级跳过 X，不卡死。

**修正（2026-06-13，曾误诊别再踩）**：早先决策记录把"X 返回 0"归因为"bird-search 在 Node v23 语法不兼容、待修"——**查实是误诊**。X 在 v23 完全正常（`search_x` 实拉 12 条）。真因是本机有两个 node：episode-runner 旧 PATH 让 `node` 解析到 `/usr/local/bin/node`（**v16**，太老跑不了 `import … with {type:'json'}`），bird-search 静默返 0；当晚那次还叠加"扫描时 cookie 尚未提取"。已修：episode-runner 把 nvm 最新 node 插到 /usr/local/bin 之前；`bin/doctor.sh` 加 node≥18 守卫，`bin/doctor.sh --x` 真拉一次验证 X。教训：**别信 agent 对失败原因的口头归因，复现了再下结论**。
两个 cookie 提取坑沉淀在 `tools/x_cookies.py`：①登录态常不在 Chrome `Default` profile（脚本扫全部 profile 按最近使用逐个试）；②首次取 Keychain 密钥有 10s 超时，来不及点就先手动 `security find-generic-password -w -s "Chrome Safe Storage" >/dev/null` 弹窗点允许再跑。

约束与权衡：
- 仅 macOS。首次提取 Keychain 可能弹窗，点允许。`--browser` 可指定 chrome/brave/firefox/safari/auto。
- 用登录态抓 X 违反其 ToS，有限流/封号风险，赌的是你自己的 X 账号。
- `auth_token` 是密码级凭证：只落 `state/x-cookies.env`(gitignored, 0600)，`tools/x_cookies.py` 不打印其值。

## 远程控制台（手机运营）

`bin/console.sh` 背后是一个常驻 paseo agent「papergirl 控制台」（id 存 state/.console-agent-id），
锁定本项目，懂四类操作：喂数据 / 查状态 / 看复盘 / 触发补跑。一句话自然语言驱动。

```bash
bin/console.sh "讲 prompt injection 那篇 阅读35 在看2 转发3 涨粉1"   # 喂数据
bin/console.sh "今天跑了吗？草稿箱有啥"                              # 查状态
bin/console.sh "这周哪篇在看率最高"                                  # 看复盘
bin/console.sh "补跑 am"                                            # 后台补跑（飞书通知完成）
bin/console.sh --image ~/Desktop/wx.png "喂这个"                    # 截图喂数据
```

**手机端**：装 Paseo App（或 app.paseo.sh），Mac 上 `paseo onboard` 出二维码扫码配对，
之后在 App 里直接和「papergirl 控制台」对话——和上面终端用法一样，只是从手机。
daemon 已挂中继 `wss://relay.paseo.sh`。**前提：Mac 醒着 + paseo daemon 在跑**（agent 在 Mac 上执行命令）；
要随时可用就别让 Mac 休眠。

## 环境依赖

- `claude`（Claude Code CLI，episode 主体）
- `bun`（微信 SDK）、`python3`（工具脚本；last30days 标称 3.12+，3.11 大部分可用，异常优先怀疑版本）
- 生图走 `.env` 的 IMAGE_API_*（OpenAI-compatible chat/completions，返回 base64 或图链）
- last30days 免费源（Reddit/HN/GitHub）零配置；X/TikTok 等增强源见其 SKILL.md，可选

## 开源前检查单

- [ ] `.env` 从未入库（`git log --all -- .env` 为空），`gitleaks` 过一遍
- [ ] `state/published.json` 与 `drafts/` 是否清空看个人意愿
- [ ] vendored 两处 LICENSE / UPSTREAM.md 完整
- [ ] README 的 quickstart 在干净机器可复现
