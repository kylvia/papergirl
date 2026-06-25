# examples/ — 一期 episode 的产出长什么样

papergirl 跑完一期，除了一篇成稿，还会沿途写下**可审计的过程记录**。正常运行时这些落在
gitignored 的 `drafts/` 与 `state/runs/`；这里放一份**脱敏的样例**，让你 clone 后不必先跑
全流程，就能看清产出物的结构与文风。

## `2026-01-01-sample/`

| 文件 | 对应阶段 | 正常落点 |
|---|---|---|
| `draft.md` | 写稿 | `drafts/{date}-<slug>.md` |
| `cover.png` | 配图 | `drafts/{date}-<slug>-cover.png` |
| `decision.md` | 定题 | `state/runs/{date}-{slot}-decision.md` |
| `brief.md` | 深研 | `state/runs/{date}-{slot}-brief.md` |
| `gates.md` | 写稿自检 | `state/runs/{date}-{slot}-gates.md` |

> 内容均为**说明性占位**（来源是示意链接、不含真实发布数据），仅演示结构。
> 真跑一期请见根 `README.md` 的 Quickstart；流程本体是 `prompts/episode.md`。

## 拿这份样例试 vault 导出（零凭证）

```bash
PUBLISHER=vault python3 tools/push.py examples/2026-01-01-sample/draft.md \
  --title "AI 把这个函数写得很漂亮，只有一个问题——它是错的" \
  --cover examples/2026-01-01-sample/cover.png
# → 在 drafts/vault/ 下生成自包含 markdown bundle（note.md + assets/）
```
