# SailZen 环境变量参考文档

> **版本**: v3.0 | **更新**: 2026-11-22 | **权威模板**: [`.env.template`](../.env.template)
> **双环境区分指南**: [doc/maintain/DevOps.md](./maintain/DevOps.md)

---

## 1. 环境文件与加载机制

`server.py` 通过 `sail/utils.py` 中的 `read_env(mode)` 根据**启动参数**显式选择环境文件，并自动写入 `ENV` 环境变量：

| 启动命令 | 加载文件 | `ENV` 值 | 适用环境 |
|---|---|---|---|
| `uv run server.py --dev` | `.env.dev` | `dev` | Windows 本地开发调试机（连接本地 PG 或 SQLite） |
| `uv run server.py --debug` | `.env.debug` | `debug` | 本地深度排障（最详细日志） |
| `uv run server.py`（无参数） | `.env.prod` | `prod` | 公网 Linux 云服务器生产环境（systemd 托管） |

初始化方法：

```powershell
Copy-Item .env.template .env.dev    # 本地开发机
# 云端服务器请单独创建并严格保护 .env.prod
```

---

## 2. 快速参考表

### 服务器与鉴权

| 变量名 | 必需 | 默认值 | 说明 |
|---|---|---|---|
| `SERVER_HOST` | ❌ | `0.0.0.0` | 监听地址（`server.py`） |
| `SERVER_PORT` | ❌ | `1974` | 监听端口（`.env.template` 示例为 `4399`，生产常用 `1974`） |
| `API_ENDPOINT` | ❌ | `/api/v1` | REST API 路由前缀 |
| `SITE_DIST` | ❌ | `site_dist` | Web 前端生产构建静态目录 |
| `SERVER_DATA_DIR` | ❌ | `data` | 服务端统一数据根目录（`sail_server/config/paths.py`） |
| `SERVER_LOG_FILE` | ❌ | — | 服务端日志文件路径 |
| `SAILZEN_API_TOKEN` | 生产推荐 | 空（不鉴权） | Bearer Token，用于保护公网 API 及 Android/SailTick/CLI 通信 |
| `SAIL_SERVER_URL` | CLI/插件/SailTick | `http://localhost:8000` | 客户端访问 `sail_server` 的基础 URL |

### 数据库配置（`sail_server/db.py`）

| 变量名 | 必需 | 默认值 | 说明 |
|---|---|---|---|
| `DB_BACKEND` | ❌ | `postgres` | `postgres`（生产推荐、本地完整调试）或 `sqlite`（零配置轻量开发） |
| `POSTGRE_URI` | PG 模式必需 | — | 格式 `postgresql://user:pass@host:port/db`（程序自动转换为 `postgresql+psycopg://` 并设 `PGCLIENTENCODING=UTF8`） |
| `SQLITE_PATH` | ❌ | `data/sailzen.db` | SQLite 模式下主库文件路径 |
| `DB_CONNECT_TIMEOUT` | ❌ | `10` | PG 连接超时秒数，避免数据库不可达时无限阻塞 |

### 后台服务开关

| 变量名 | 默认值 | 说明 |
|---|---|---|
| `WEATHER_ENABLED` | `true` | 是否启动天气后台更新循环 |
| `WEATHER_UPDATE_INTERVAL_MINUTES` | `60` | 天气拉取间隔（分钟） |
| `WEATHER_FORECAST_DAYS` | `7` | 预报天数 |
| `WEATHER_RECORD_LOOKBACK_DAYS` | `3` | 过去日期实录补拉回看天数 |
| `WEATHER_CITIES` | 杭州/上海/合肥 | JSON 数组：`[{"name":...,"latitude":...,"longitude":...}]` |
| `REMINDER_ENABLED` | `true` | 是否启动提醒调度扫描循环（**本地调试建议按需设为 `false` 避免误推真机**） |

### 日志与调试（`sail_server/utils/logging_config.py`）

| 变量名 | 默认值 | 说明 |
|---|---|---|
| `LOG_MODE` | `prod` | `prod` / `dev` / `debug` |
| `LOG_LEVEL` | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` / `CRITICAL` |
| `LOG_DIR` | `logs` | 日志目录 |
| `API_DEBUG` | `false` | 记录详细 HTTP 请求/响应日志 |
| `LLM_DEBUG` | `false` | 记录详细 LLM 调用日志 |
| `DB_DEBUG` | `false` | 记录 SQLAlchemy 查询日志 |

### LLM Provider（至少配置一个以使用 AI 功能）

| Provider | 密钥变量 | 模型变量 | 默认模型 | 备注 |
|---|---|---|---|---|
| **Moonshot (Kimi)** | `MOONSHOT_API_KEY` | `MOONSHOT_MODEL` / `MOONSHOT_API_BASE` | `kimi-k2.5` | 项目全局默认；**`kimi-k2.5` 要求 `temperature=1.0`** |
| **DeepSeek** | `DEEPSEEK_API_KEY` | `DEEPSEEK_MODEL` / `DEEPSEEK_API_BASE` | `deepseek-chat` | 第一候补 / SailTick 默认主力 |
| **Google Gemini** | `GOOGLE_API_KEY` | `GOOGLE_MODEL` | `gemini-2.0-flash` | — |
| **OpenAI** | `OPENAI_API_KEY` | `OPENAI_MODEL` / `OPENAI_API_BASE` | `gpt-4o-mini` | — |
| **Anthropic** | `ANTHROPIC_API_KEY` | `ANTHROPIC_MODEL` | `claude-3-haiku-20240307` | — |
| **Ollama (本地)** | — | `OLLAMA_HOST` | `http://localhost:11434` | 本地模型可选 |

### SailTick 教练 Daemon（`sailtick/`）

| 变量名 | 默认值 | 说明 |
|---|---|---|
| `SAILTICK_CONFIG` | `sailtick.yaml` | 配置文件路径 |
| `SAILTICK_API_HOST` | `127.0.0.1` | 管理 API 绑定地址（仅本机） |
| `SAILTICK_API_PORT` | `9070` | 管理 API 端口 |
| `SAILTICK_DB_PATH` | `data/sailtick/db/sailtick.db` | 隔离 SQLite 路径（**禁止 `db_sync.py` 同步**） |
| `SAILTICK_DATA_DIR` | `data/sailtick` | handoff / runs / artifacts 目录 |
| `SAILTICK_LOG_DIR` | `logs/sailtick` | SailTick 日志目录 |
| `SAILTICK_TIMEZONE` | `Asia/Shanghai` | Tick 排程时区 |
| `SAILTICK_SELF_DEV_REPO` | — | 自我开发仓库路径（Phase 5 可选） |

### 测试与运维扩展

| 变量名 | 默认值 | 说明 |
|---|---|---|
| `SKIP_DB_TESTS` | `false` | 是否跳过依赖数据库的集成测试 |
| `ALLOW_PUSH` | 未设置 | 仅显式设为 `1` 时允许直接 `git push origin`（见 `.agents/skills/git-push/SKILL.md`） |

---

## 3. 安全注意事项

1. **严禁提交真实凭据**：`.env.dev`、`.env.prod`、`.env.debug`、`.env.ops`、`android/keystore/` 已/必须纳入 `.gitignore`。
2. **严禁混淆环境文件**：在 Windows 本地开发机上不要把 `.env.dev` 的 `POSTGRE_URI` 指向云端生产库，防止测试数据污染生产库。
3. **定期轮换公网 Token 与 API Key**，且日志中始终对数据库 URI 执行打码脱敏。
