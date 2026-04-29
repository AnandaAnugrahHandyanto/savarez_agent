# 端口说明（本地 / 协同 hermes-web-ui）

> 本文档记录本仓库 **Hermes Agent** 及常见搭配 **hermes-web-ui** 的默认端口；若你在 `~/.hermes/.env`、`config.yaml` 或启动参数里改过，以实际配置为准。

---

## Hermes（`hermes gateway` / API Server）


| 端口       | 用途                                               | 配置 / 说明                                                                                                |
| -------- | ------------------------------------------------ | ------------------------------------------------------------------------------------------------------ |
| **8642** | 网关上的 **OpenAI 兼容 HTTP API**（`/health`、`/v1/...`） | 默认 `API_SERVER_PORT=8642`；见 `gateway/platforms/api_server.py`、`OPTIONAL_ENV_VARS` 中的 `API_SERVER_PORT` |
| **9119** | 内置 Web 面板 `**hermes dashboard`**（CLI 默认）       | `hermes dashboard --port` 覆盖，源码默认见 `hermes_cli/main.py`                                              |
| **9112** | 同上（本仓库 **docker compose** 里仪表盘监听端口）        | `docker-compose.yml` 中 `dashboard` 服务固定 `--port 9112`；需与防火墙 / 安全组一致时可优先记此端口                         |


启用 8642 上的 API 需在 `~/.hermes/.env` 中配置 `API_SERVER_ENABLED=true`（或等价方式），并运行 `hermes gateway run`。

### 本仓库 `docker compose` 默认（对外绑定）

根目录 `docker-compose.yml` 在 **`network_mode: host`** 下默认：

- 网关 **API Server**：`0.0.0.0:8642`，且要求设置环境变量 **`API_SERVER_KEY`**（可在与 compose 同目录的 `.env` 里写，供 compose 替换 `${API_SERVER_KEY}`）。
- 仪表盘：**`0.0.0.0:9112`**（`--insecure`，无强认证，仅建议在可信网络或反代后使用）。本地直接跑 `hermes dashboard` 不加参数时，CLI 默认仍为 **9119**；若要统一成 9112，可执行 `hermes dashboard --port 9112`（配合本机防火墙放行）。

本机 **ufw** 放行可与上述一致：

```bash
chmod +x scripts/ufw_allow_hermes_ports.sh
./scripts/ufw_allow_hermes_ports.sh
```

（默认放行 **8642** + **9112**；若仪表盘用 CLI 默认端口，可执行 `HERMES_DASHBOARD_PORT=9119 ./scripts/ufw_allow_hermes_ports.sh`。）

---

## hermes-web-ui（独立前端 / BFF，非本仓库）

若将 [hermes-web-ui](https://github.com/EKKOLearnAI/hermes-web-ui) 与本机 Hermes 协同，常见默认如下：


| 端口       | 用途                | 说明                                                                     |
| -------- | ----------------- | ---------------------------------------------------------------------- |
| **8648** | BFF（Koa）          | 环境变量 `PORT`，默认约 8648；通过 `UPSTREAM` 指向 Hermes，如 `http://127.0.0.1:8642` |
| **5173** | Vite 开发前端         | `npm run dev` 时常见，以终端输出为准                                              |
| **6060** | Docker Compose 示例 | 文档中由 `PORT` 驱动，非固定                                                     |


---

## 协同关系（简图）

```
浏览器 → hermes-web-ui BFF (:8648 等) → UPSTREAM → Hermes API Server (:8642)
```

可选：本仓库 **compose** 下图表盘为 **9112**；本机 `hermes dashboard` 默认可占 **9119**。端口不同即可与上述同时存在。

---

## 防火墙 / 安全提示

- **127.0.0.1** 仅本机访问时风险较低；若将 **8642** 或 BFF 端口绑到 `0.0.0.0` 或对外网开放，请配置 `**API_SERVER_KEY`** 等并评估暴露面。

---

## 变更记录


| 日期         | 说明             |
| ---------- | -------------- |
| 2026-04-28 | docker compose 默认对外绑定 8642 + 9112；增加 ufw 脚本说明 |
| 2026-04-27 | 初版：汇总默认端口与协同关系 |


