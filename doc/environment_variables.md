# SailZen 环境变量参考文档

本文档列出项目中所有使用的环境变量及其用途。

## 快速参考表

| 变量名 | 必需 | 默认值 | 用途 |
|--------|------|--------|------|
| `POSTGRE_URI` | ✅ | - | PostgreSQL 数据库连接 URI |
| `MOONSHOT_API_KEY` | ⚠️ | - | Moonshot (Kimi) API 密钥 |
| `OPENAI_API_KEY` | ❌ | - | OpenAI API 密钥 |
| `ANTHROPIC_API_KEY` | ❌ | - | Anthropic (Claude) API 密钥 |
| `GOOGLE_API_KEY` | ❌ | - | Google Gemini API 密钥 |
| `SERVER_PORT` | ❌ | 1974 | 服务器监听端口 |
| `SERVER_HOST` | ❌ | 0.0.0.0 | 服务器监听地址 |
| `LOG_MODE` | ❌ | prod | 日志模式 (prod/dev/debug) |
| `LOG_LEVEL` | ❌ | INFO | 日志级别 |
| `LOG_DIR` | ❌ | logs | 日志文件目录 |

> ✅ 必需 | ⚠️ 至少需要一个 | ❌ 可选

---

## 详细说明

### 服务器配置

#### `SERVER_PORT`
- **类型**: 整数
- **默认值**: 1974
- **说明**: 服务器监听的端口号
- **使用位置**: `server.py`

#### `SERVER_HOST`
- **类型**: 字符串
- **默认值**: `0.0.0.0`
- **说明**: 服务器监听的 IP 地址
- **使用位置**: `server.py`

#### `API_ENDPOINT`
- **类型**: 字符串
- **默认值**: `/api/v1`
- **说明**: API 端点的基础路径
- **使用位置**: `server.py`, `sail_server/sample_client.py`

#### `SITE_DIST`
- **类型**: 字符串
- **默认值**: `site_dist`
- **说明**: 前端站点静态文件目录
- **使用位置**: `server.py`

---

### 数据库配置

#### `POSTGRE_URI`
- **类型**: 字符串
- **必需**: 是
- **格式**: `postgresql://username:password@host:port/database`
- **示例**: `postgresql://postgres:password@localhost:5432/main`
- **使用位置**: `sail_server/db.py`, `sail_server/migration/verify_migration.py`

#### `PGCLIENTENCODING`
- **类型**: 字符串
- **默认值**: `UTF8` (程序自动设置)
- **说明**: PostgreSQL 客户端编码
- **使用位置**: `sail_server/db.py`, `sail_server/migration/verify_migration.py`

---

### 日志配置

#### `LOG_MODE`
- **类型**: 字符串
- **默认值**: `prod`
- **可选值**: 
  - `prod`: 生产模式，只记录警告级别以上
  - `dev`: 开发模式，INFO 级别，彩色输出
  - `debug`: 调试模式，最详细的日志
- **使用位置**: `sail_server/utils/logging_config.py`, `server.py`

#### `LOG_LEVEL`
- **类型**: 字符串
- **默认值**: `INFO`
- **可选值**: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`
- **使用位置**: `sail_server/utils/logging_config.py`

#### `LOG_DIR`
- **类型**: 字符串
- **默认值**: `logs`
- **说明**: 日志文件存储目录
- **使用位置**: `sail_server/utils/logging_config.py`

#### `API_DEBUG`
- **类型**: 布尔值 (`true`/`false`)
- **默认值**: `false`
- **说明**: 启用 API 请求/响应详细日志
- **日志文件**: `logs/api_requests.log`
- **使用位置**: `sail_server/utils/logging_config.py`, `sail_server/utils/llm/client.py`

#### `LLM_DEBUG`
- **类型**: 布尔值 (`true`/`false`)
- **默认值**: `false`
- **说明**: 启用 LLM API 调用详细日志
- **日志文件**: `logs/llm_debug.log`
- **使用位置**: `sail_server/utils/logging_config.py`, `sail_server/utils/llm/client.py`

#### `DB_DEBUG`
- **类型**: 布尔值 (`true`/`false`)
- **默认值**: `false`
- **说明**: 启用数据库查询详细日志
- **日志文件**: `logs/db_queries.log`
- **使用位置**: `sail_server/utils/logging_config.py`

#### `LLM_LOG_LEVEL`
- **类型**: 字符串
- **默认值**: `INFO`
- **说明**: LLM 专用日志级别
- **使用位置**: `sail_server/utils/llm/client.py`

#### `LLM_LOG_PATH`
- **类型**: 字符串
- **默认值**: `logs/llm_debug.log`
- **说明**: LLM 调试日志文件路径
- **使用位置**: `sail_server/utils/llm/client.py`

---

### LLM Provider 配置

#### Moonshot (Kimi) - 项目默认推荐

##### `MOONSHOT_API_KEY`
- **类型**: 字符串
- **说明**: Moonshot API 密钥
- **获取方式**: https://platform.moonshot.cn/
- **使用位置**: 
  - `sail_server/utils/llm/client.py`
  - `sail_server/utils/llm/gateway.py`
  - `scripts/verify_llm_backend.py`
  - `scripts/validate_kimi.py`
  - `scripts/demo_llm_outline_extraction.py`

##### `MOONSHOT_MODEL`
- **类型**: 字符串
- **默认值**: `kimi-k2.5`
- **可选值**: `kimi-k2.5`, `kimi-k2`, `kimi-k1.5`, `kimi-latest`
- **特殊说明**: `kimi-k2.5` 只支持 `temperature=1`
- **使用位置**: `sail_server/utils/llm/client.py`, `sail_server/utils/llm/gateway.py`

##### `MOONSHOT_API_BASE`
- **类型**: 字符串
- **默认值**: `https://api.moonshot.cn/v1`
- **说明**: API 基础 URL，可用于代理
- **使用位置**: `sail_server/utils/llm/client.py`, `sail_server/utils/llm/gateway.py`

#### OpenAI

##### `OPENAI_API_KEY`
- **类型**: 字符串
- **说明**: OpenAI API 密钥
- **获取方式**: https://platform.openai.com/
- **使用位置**: 
  - `sail_server/utils/llm/client.py`
  - `sail_server/utils/llm/gateway.py`
  - `tests/llm_integration/test_llm_connection.py`

##### `OPENAI_MODEL`
- **类型**: 字符串
- **默认值**: `gpt-4`
- **可选值**: `gpt-4o`, `gpt-4o-mini`, `gpt-4-turbo`, `gpt-4`, `gpt-3.5-turbo`
- **使用位置**: `sail_server/utils/llm/client.py`, `sail_server/utils/llm/gateway.py`

##### `OPENAI_API_BASE`
- **类型**: 字符串
- **默认值**: `https://api.openai.com/v1`
- **说明**: API 基础 URL，可用于代理或 Azure OpenAI
- **使用位置**: `sail_server/utils/llm/client.py`, `sail_server/utils/llm/gateway.py`

#### Anthropic (Claude)

##### `ANTHROPIC_API_KEY`
- **类型**: 字符串
- **说明**: Anthropic API 密钥
- **获取方式**: https://console.anthropic.com/
- **使用位置**: 
  - `sail_server/utils/llm/client.py`
  - `sail_server/utils/llm/gateway.py`
  - `tests/llm_integration/test_llm_connection.py`

##### `ANTHROPIC_MODEL`
- **类型**: 字符串
- **默认值**: `claude-3-opus-20240229`
- **可选值**: `claude-3-opus-20240229`, `claude-3-sonnet-20240229`, `claude-3-haiku-20240307`
- **使用位置**: `sail_server/utils/llm/client.py`, `sail_server/utils/llm/gateway.py`

#### Google Gemini

##### `GOOGLE_API_KEY`
- **类型**: 字符串
- **说明**: Google AI Studio API 密钥
- **获取方式**: https://aistudio.google.com/
- **使用位置**: 
  - `sail_server/utils/llm/client.py`
  - `sail_server/utils/llm/gateway.py`
  - `tests/llm_integration/`

##### `GOOGLE_MODEL`
- **类型**: 字符串
- **默认值**: `gemini-2.0-flash`
- **可选值**: `gemini-2.0-flash`, `gemini-2.0-flash-lite`, `gemini-1.5-flash`, `gemini-1.5-pro`
- **使用位置**: `sail_server/utils/llm/client.py`, `sail_server/utils/llm/gateway.py`

##### `GOOGLE_GENAI_USE_VERTEXAI`
- **类型**: 布尔值
- **默认值**: `False`
- **说明**: 是否使用 Google Cloud Vertex AI
- **使用位置**: `tests/llm_integration/run_validation.py`

##### `GOOGLE_GENAI_DISABLE_AFC`
- **类型**: 布尔值
- **默认值**: `True`
- **说明**: 是否禁用自动函数调用
- **使用位置**: `tests/llm_integration/run_validation.py`

---

### 本地 LLM 配置

#### `OLLAMA_HOST`
- **类型**: 字符串
- **默认值**: `http://localhost:11434`
- **说明**: Ollama 本地服务地址
- **使用位置**: `tests/llm_integration/validators/connection.py`

---

### 测试配置

#### `SKIP_DB_TESTS`
- **类型**: 布尔值 (`true`/`false`)
- **默认值**: `false`
- **说明**: 跳过需要数据库的测试
- **使用位置**: `tests/llm_integration/test_task_flow.py`

---

## 环境配置文件

项目支持以下环境配置文件（按优先级排序）：

1. `.env.debug` - 调试环境（最高优先级）
2. `.env.dev` - 开发环境
3. `.env.prod` - 生产环境
4. 系统环境变量

### 创建环境配置文件

```bash
# 开发环境
cp .env.template .env.dev

# 生产环境
cp .env.template .env.prod
```

### 加载环境变量

```python
from dotenv import load_dotenv

# 根据环境加载
def load_env():
    if os.path.exists(".env.debug"):
        load_dotenv(".env.debug")
        print("Loaded .env.debug")
    elif os.path.exists(".env.dev"):
        load_dotenv(".env.dev")
        print("Loaded .env.dev")
    elif os.path.exists(".env.prod"):
        load_dotenv(".env.prod")
        print("Loaded .env.prod")
```

---

## 故障排除

### 数据库连接失败

检查 `POSTGRE_URI` 格式：
```bash
# 本地数据库
POSTGRE_URI=postgresql://postgres:password@localhost:5432/main

# 远程数据库
POSTGRE_URI=postgresql://user:pass@host:port/dbname
```

### LLM API 调用失败

1. 检查 API Key 是否正确设置
2. 检查网络连接
3. 查看日志文件了解详细错误：
   - `logs/llm_debug.log` - LLM 调试日志
   - `logs/sailzen.log` - 主日志

### 日志不输出

检查 `LOG_MODE` 和 `LOG_LEVEL` 设置：
```bash
# 开发环境建议
LOG_MODE=dev
LOG_LEVEL=DEBUG
API_DEBUG=true
LLM_DEBUG=true
```

---

## 安全注意事项

1. **永远不要提交包含真实 API Key 的配置文件到版本控制**
2. **生产环境应该使用强密码保护数据库**
3. **定期轮换 API Key**
4. **使用 `.gitignore` 忽略 `.env.*` 文件**

```gitignore
# .gitignore
.env.dev
.env.prod
.env.debug
logs/
.cache/
```
