---
name: sailzen-ai-text-import
description: AI驱动的智能文本导入工具，用于解析txt小说文件的章节结构。支持采样分析学习章节模式、智能识别特殊章节（楔子、番外等）、过滤广告噪音、异常章节检测，并提供人机确认界面。适用于各种非标准格式的小说文本导入。
---

# SailZen AI 文本导入工具

智能解析各种格式的小说文本，自动识别章节结构，支持人机确认的导入流程。

## 何时使用此 Skill

- 需要导入 txt 格式的小说文件到 SailZen 数据库
- 文件包含非标准章节格式（楔子、番外、作者感言等）
- 纯规则匹配无法正确识别章节
- 需要过滤广告、推广链接等噪音内容
- 需要检测并处理异常章节（过长或过短）

## 核心功能

### 1. 文本预清理 (`text_cleaner.py`)

自动处理常见的文本质量问题：

| 问题类型 | 处理方式 |
|---------|---------|
| 编码问题 | 自动检测并统一转换为 UTF-8 |
| URL/链接 | 移除所有网址、推广链接 |
| 广告内容 | 识别并移除含关键词的广告行 |
| 纯符号行 | 清理分隔线、装饰符号 |
| 乱码检测 | 标记并移除锟斤拷等乱码字符 |
| 空白字符 | 标准化换行符，合并连续空行 |

### 2. AI 章节解析 (`ai_chapter_parser.py`)

智能识别章节结构：

**采样分析流程：**
1. 从文本开头、中间、结尾各采样 ~3000 字符
2. 提交 LLM 分析学习章节标题模式
3. 生成匹配正则表达式
4. 应用模式解析全部章节

**特殊章节识别：**
- 前置章节：楔子、序章、引言、开篇
- 标准章节：第X章、Chapter X
- 过渡章节：间章、插曲
- 后置章节：尾声、后记、终章
- 番外章节：番外、外传、特别篇
- 作者相关：作者的话、感言、请假条

**异常检测：**
- 超长章节（> avg + 3σ）：可能包含多个未切分的章节
- 超短章节（< avg - 3σ 或 <100字）：可能是广告或作者说明

### 3. 人机确认界面 (`import_with_ai.py`)

导入前展示详细信息供用户确认：

```
══════════════════════════════════════════════════════
  📊 章节分析结果
══════════════════════════════════════════════════════
  总章节数: 1,234
  总字数:   2,567,890
  平均每章: 2,081 字
  最短章节: 156 字
  最长章节: 15,432 字
──────────────────────────────────────────────────────

  拆分规则:
    • 识别到标准中文章节模式
    • 使用 4 个正则模式
    • prologue: 2 章 (楔子、序章)
    • epilogue: 1 章 (尾声)
    • extra: 3 章 (番外)

  ⚠️ 警告:
    • 检测到 5 个异常章节
    • 存在极短章节（最短 156 字）

══════════════════════════════════════════════════════
  📖 前 3 章预览
══════════════════════════════════════════════════════

  [0] 楔子 [PROLOGUE]
      字数: 1,234 | 位置: 0-5,678
      开头: 这是一个楔子的开头内容...
      结尾: ...楔子的结尾内容

  [1] 第一章 风云初起 [STANDARD]
      字数: 2,567 | 位置: 5,678-15,432
      开头: 风起云涌，江湖变幻...
      结尾: ...第一章完

  ...

是否确认导入? (y/n/e=编辑):
```

## 使用方法

### 基本用法

```bash
# 使用 AI 分析并导入
uv run scripts/import_with_ai.py novel.txt --title "小说标题" --author "作者名"

# 仅预览分析结果（不导入）
uv run scripts/import_with_ai.py novel.txt --title "小说标题" --preview

# 使用规则解析（不使用 AI）
uv run scripts/import_with_ai.py novel.txt --title "小说标题" --no-ai

# 跳过确认直接导入
uv run scripts/import_with_ai.py novel.txt --title "小说标题" --yes
```

### 参数说明

| 参数 | 说明 | 示例 |
|------|------|------|
| `file` | 要导入的 txt 文件 | `novel.txt` |
| `--title, -t` | 作品标题（默认用文件名） | `--title "斗破苍穹"` |
| `--author, -a` | 作者名 | `--author "天蚕土豆"` |
| `--edition, -e` | 版本名称 | `--edition "精校版"` |
| `--preview, -p` | 仅预览不导入 | `--preview` |
| `--no-ai` | 禁用 AI，仅使用规则 | `--no-ai` |
| `--yes, -y` | 跳过确认直接导入 | `--yes` |

### 交互式编辑

在确认界面输入 `e` 进入编辑模式：

```
编辑 > l                    # 列出所有章节
编辑 > d 5                  # 删除第 5 章
编辑 > t 10 extra           # 将第 10 章改为番外类型
编辑 > q                    # 完成编辑
```

## 参考资料

- [章节类型参考](references/chapter_types.md) - 完整的章节类型定义和处理规则
- [噪音模式参考](references/noise_patterns.md) - 常见广告和噪音内容的识别模式

## 扩展：接入 LLM

当前实现支持通过 `llm_client` 参数接入 LLM：

```python
from scripts.ai_chapter_parser import AIChapterParser

# 你的 LLM 客户端
class MyLLMClient:
    def generate(self, prompt: str) -> str:
        # 调用你的 LLM API
        response = call_your_llm(prompt)
        return response

# 使用自定义 LLM
parser = AIChapterParser(llm_client=MyLLMClient())
```

支持的提供商：
- Google Gemini
- OpenAI GPT
- Moonshot AI
- 其他兼容 OpenAI API 格式的服务

## 注意事项

1. **大文件处理**：超过 10MB 的文件会自动使用采样分析，不会全文提交给 LLM
2. **AI 成本**：AI 模式会消耗 LLM tokens，大文件建议先用 `--preview` 测试
3. **结果检查**：即使使用 AI，也建议通过预览界面检查识别结果
4. **数据库导入**：当前版本生成分析结果，实际数据库导入需要接入 `sail_server`

## 文件结构

```
sailzen-ai-text-import/
├── SKILL.md                          # 本文件
├── scripts/
│   ├── text_cleaner.py               # 文本预清理
│   ├── ai_chapter_parser.py          # AI 章节解析
│   └── import_with_ai.py             # 主程序
└── references/
    ├── chapter_types.md              # 章节类型参考
    └── noise_patterns.md             # 噪音模式参考
```
