# publishers — 发布适配器

推稿的唯一入口是 `tools/push.py`（CLAUDE.md 硬规则 #7）。它按 `PUBLISHER` 把请求分发到
这里的某个适配器，从而把「发到哪」与流程其余部分解耦。

```
push.py ──(PublishRequest)──▶ get_publisher(name) ──▶ <adapter>.publish(req) -> int
```

## 内置适配器

| name | 凭证 | 说明 |
|---|---|---|
| `wechat` | 需 `WECHAT_APP_ID/SECRET`(+可选 `WECHAT_PROXY_URL`) | **默认**。vendored WeChat SDK + per-process 微信代理 + 文末关注卡。 |
| `vault` | 无 | 零依赖。把成稿导出成自包含 markdown bundle（`note.md` + `assets/`），写到 `$PAPERGIRL_VAULT_DIR`（默认 `drafts/vault/`）。没有微信账号也能跑通全流程；也是 files-first / Obsidian 视角的导出。 |

## 选择适配器

```bash
# 默认 wechat（与历史行为字节等价）
python3 tools/push.py drafts/x.md --title "标题" --cover drafts/x-cover.png

# 切到 vault（无需任何凭证）
PUBLISHER=vault python3 tools/push.py drafts/x.md --title "标题" --cover drafts/x-cover.png
# 或
python3 tools/push.py drafts/x.md --title "标题" --cover drafts/x-cover.png --publisher vault
```

## 加一个新适配器（如 Substack / Ghost / Telegram）

1. 在本目录加 `<name>.py`，暴露 `def publish(req: PublishRequest) -> int:`（0=成功）。
   从 `PublishRequest`（见 `__init__.py`）取 `md / title / summary / cover / author / theme /
   dry_run / verbose / follow_card`，按需使用。
2. 在 `__init__.py` 的 `get_publisher()` 注册一行。
3. 凭证只从 `os.environ` 读（由 push.py 从 `.env` 注入），不要硬编码、不要打印。

约定：`dry_run` 不产生外部副作用；推送成功在 stdout 末尾给一行机器可读结果。
