# 给微信推送配代理服务器

只有 `PUBLISHER=wechat` 这条路、且 papergirl 跑的机器出口 IP 进不了公众号白名单时才需要。
`vault` 路径、扫描、生图都**不**走代理。

## 你到底需不需要代理？

微信公众号 API 校验**调用方公网 IP**（公众号后台 → 开发 → 基本配置 → IP 白名单）。

```
papergirl 跑在哪台机器？
├─ 这台的公网出口 IP 固定、能加进白名单 → 直接加白，WECHAT_PROXY_URL 留空走直连，不用代理
└─ 这台 IP 动态/加不了白（笔记本、家宽、容器） → 借一台固定公网 IP 的服务器做正向代理，把【那台】的 IP 加白
```

> 在跑 papergirl 的**同一台机器**上起代理 = 出口还是本机 IP，等于没起。代理的意义是「借另一台固定 IP 的出口」。

下面假设你有一台**固定公网 IP 的服务器**（记其 IP 为 `PROXY_PUBLIC_IP`），在它上面起正向代理。

---

## 方案 A：tinyproxy（推荐，最简，支持只放行微信域 + 认证）

在代理服务器上：

```bash
# 1. 安装
sudo apt-get install -y tinyproxy        # Debian/Ubuntu
# brew install tinyproxy                  # macOS

# 2. 写配置 /etc/tinyproxy/tinyproxy.conf
```

`/etc/tinyproxy/tinyproxy.conf`（最小安全版）：

```conf
User tinyproxy
Group tinyproxy
Port 8888
Timeout 600

# 谁能连这个代理：只放行 papergirl 所在机器（换成你的来源 IP；不确定就先只留 127.0.0.1 本机测）
Allow 127.0.0.1
Allow <PAPERGIRL_MACHINE_IP>

# 认证（强烈建议，防代理被滥用）
BasicAuth papergirl <STRONG_PASSWORD>

# 只放行到微信域，其它目标一律拒绝
FilterDefaultDeny Yes
FilterExtended On
Filter "/etc/tinyproxy/filter"

# CONNECT 只允许 443（HTTPS），堵掉其它端口
ConnectPort 443
```

`/etc/tinyproxy/filter`（允许的目标域，正则逐行）：

```
weixin\.qq\.com
```

```bash
# 3. 起服务
sudo systemctl enable --now tinyproxy
sudo systemctl restart tinyproxy

# 4. 防火墙：只让 papergirl 机器访问 8888（云主机安全组同理）
sudo ufw allow from <PAPERGIRL_MACHINE_IP> to any port 8888
```

papergirl 端 `.env`：

```bash
WECHAT_PROXY_URL=http://papergirl:<STRONG_PASSWORD>@<PROXY_PUBLIC_IP>:8888
```

---

## 方案 B：Caddy forward_proxy（已经在用 Caddy 时）

需要带 forwardproxy 插件的 Caddy（标准发行版不含）：

```bash
xcaddy build --with github.com/caddyserver/forwardproxy
```

Caddyfile：

```caddyfile
{
  order forward_proxy before reverse_proxy
}

:8888 {
  forward_proxy {
    basic_auth papergirl <STRONG_PASSWORD>
    hide_ip
    hide_via
  }
}
```

⚠️ Caddy forwardproxy **不方便按目标域做白名单**，「只放行微信」这条做不到——只能靠
`basic_auth` + 防火墙（只让 papergirl 机器连 8888）兜底。要「只放行微信域」选方案 A 更稳。

papergirl 端 `.env` 同样：`WECHAT_PROXY_URL=http://papergirl:<STRONG_PASSWORD>@<PROXY_PUBLIC_IP>:8888`

---

## 必做：把代理出口 IP 加进公众号白名单

公众号后台 → 开发 → 基本配置 → **IP 白名单** → 填入 `PROXY_PUBLIC_IP`。

不加白会撞 `40164`（IP 不在白名单）——这是逻辑错误，runner 不重试、直接失败。

## 验证

```bash
# 在代理服务器本机：能 CONNECT 微信、不能连别的
curl -x http://papergirl:<PASS>@127.0.0.1:8888 -sI https://api.weixin.qq.com/ | head -1   # 应有响应
curl -x http://papergirl:<PASS>@127.0.0.1:8888 -sI https://example.com/      | head -1   # 应被拒(Filter)

# 在 papergirl 机器：真推一篇进草稿箱（不群发）
python3 tools/push.py <你的稿.md> --title ... --cover ... --verbose
#   成功标准：--verbose 显示 proxy=on、拿到 media_id、无 40164 告警
```

## 安全要点

- **代理只放行微信域**（方案 A 的 Filter）：避免变成开放代理被滥用。
- **加认证 + 防火墙限来源**：`BasicAuth` + 只允许 papergirl 机器访问代理端口。
- 代理凭证算密码级：`WECHAT_PROXY_URL` 只住 `.env`（gitignored, 0600），别进 git、别打印。
- **绝不全局 `export HTTPS_PROXY`**：代理只能由 `tools/push.py` per-process 注入给微信推送子进程；全局了会让生图/扫描也走代理被 filter 403（CLAUDE.md 硬规则 #2）。

## 交给 Claude Code 自动起

把这份文档 + 一台固定公网 IP 服务器的 SSH 访问交给你的 Claude Code，让它照方案 A 装配 tinyproxy
基本能两三条命令搞定。**它替你做不了的两步**：① 提供那台固定公网 IP（基建）；② 去公众号后台
网页填 IP 白名单（手动）。这两步仍需你自己来。
