# Skill: opencode-kimi-config

在 OpenCode 中正确配置和使用 Kimi (Moonshot) 模型。

## 关键结论

### 1. `--no-think` 是幻觉

**OpenCode 没有 `--no-think` 启动参数。**

之前代码中出现的 `--no-think` 是 AI 模型的幻觉产物，
在 `sail_bot/session_manager.py` 第 316 行被错误添加。

**正确的启动命令：**
```bash
opencode-cli serve --hostname 127.0.0.1 --port <port>
```

### 2. Kimi K2.5 思考能力配置

Kimi K2.5 模型**默认启用**思考能力，通过 API 参数控制：

**启用思考（默认）：**
```json
{
  "thinking": {
    "type": "enabled"
  }
}
```

**禁用思考：**
```json
{
  "thinking": {
    "type": "disabled"
  }
}
```

### 3. 全局配置文件位置

**Windows:**
```
%LOCALAPPDATA%\OpenCode\opencode.json
```
实际路径示例：
```
C:\Users\<username>\AppData\Local\OpenCode\opencode.json
```

**macOS/Linux:**
```
~/.config/opencode/opencode.json
```

### 4. 完整配置示例

```json
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "moonshot": {
      "models": {
        "kimi-k2.5": {
          "options": {
            "temperature": 1.0,
            "thinking": {
              "type": "disabled"
            }
          }
        }
      }
    }
  }
}
```

## 重要限制

1. **temperature 固定为 1.0**: Kimi K2.5 只支持 `temperature=1.0`，其他值会被忽略或报错
2. **使用 reasoning_content**: 思考内容通过 `reasoning_content` 字段返回，不是标准 OpenAI API 的一部分
3. **max_tokens 建议 >= 16000**: 确保有足够空间输出思考和回答

## 参考文档

- OpenCode Providers: https://opencode.ai/docs/providers
- OpenCode Models: https://opencode.ai/docs/models
- Kimi Thinking Model: https://platform.moonshot.cn/docs/guide/use-kimi-k2-thinking-model

## 已修复的问题

### 修复记录

**文件**: `sail_bot/session_manager.py`  
**问题**: 第 316 行错误添加了 `--no-think` 参数  
**修复**: 删除该参数

```python
# 修复前（错误）
cmd = [
    "opencode-cli",
    "serve",
    "--hostname",
    "127.0.0.1",
    "--port",
    str(session.port),
    "--no-think",  # <-- 幻觉参数，已删除
]

# 修复后（正确）
cmd = [
    "opencode-cli",
    "serve",
    "--hostname",
    "127.0.0.1",
    "--port",
    str(session.port),
]
```

## 参考文档

- OpenCode Providers: https://opencode.ai/docs/providers
- OpenCode Models: https://opencode.ai/docs/models
- Kimi Thinking Model: https://platform.moonshot.cn/docs/guide/use-kimi-k2-thinking-model

## 关于文件路径编辑

**注意**：关于 Windows 文件路径编辑错误的经验教训已移至通用开发指南：
- 文件：`.opencode/skills/sailzen-dev-guide/references/troubleshooting.md`
- 章节：AI Agent 文件编辑教训
