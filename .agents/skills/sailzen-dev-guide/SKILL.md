---
name: sailzen-dev-guide
description: SailZen 项目开发环境指南。包含项目结构、常用命令（uv/pnpm）、Windows PowerShell 开发注意事项、编码问题处理、故障排除。适用于 Windows 环境下使用 Python 3.13 + uv + PostgreSQL + TypeScript/pnpm 技术栈的开发工作。
---

# SailZen 开发环境指南

SailZen 项目的开发环境配置和最佳实践。

## 何时使用此 Skill

- 在 SailZen 项目中进行开发工作
- 需要运行 Python/TypeScript 代码
- 遇到 Windows PowerShell 命令问题
- 处理编码或数据库连接问题
- 需要了解项目结构或常用命令

## 开发环境要求

- **操作系统**: Windows (PowerShell)
- **Python**: >= 3.13
- **包管理器**: uv (Python), pnpm (Node.js)
- **数据库**: PostgreSQL
- **项目位置**: `D:\ws\repos\SailZen`

## 关键原则

### 1. 始终使用 `uv run`

```bash
# ❌ 错误 - 使用系统 Python
python script.py

# ✅ 正确 - 使用 uv 运行
uv run python script.py
uv run python -c "print('hello')"
uv run server.py
```

### 2. PowerShell 命令分隔符

```powershell
# ❌ 错误（Linux 语法）
cd dir && python script.py

# ✅ 正确（PowerShell 语法）
cd dir; python script.py

# 或分两行
cd dir
python script.py
```

### 3. 环境变量设置

```powershell
# 临时设置（当前会话）
$env:POSTGRE_URI="postgresql://postgres:zzh666@localhost:5432/main"

# 验证
$env:POSTGRE_URI
```

### 4. 路径处理

```python
# ❌ 错误 - 会被转义
path = "D:\path\to\file.txt"  # \t 变成制表符

# ✅ 正确 - 原始字符串
path = r"D:\path\to\file.txt"

# ✅ 正确 - 正斜杠
path = "D:/path/to/file.txt"
```

### 5. 编码问题

```powershell
# 如果终端显示乱码（���）
chcp 65001
```

乱码通常是**显示问题**，不影响实际数据。

## 快速开始

### 运行 Python 代码

```bash
# 1. 确保在项目根目录
cd D:\ws\repos\SailZen

# 2. 设置环境变量
$env:POSTGRE_URI="postgresql://postgres:zzh666@localhost:5432/main"

# 3. 运行代码
uv run python your_script.py

# 或交互式
uv run python
```

### 导入文本到数据库

```bash
# 使用 AI 文本导入 skill
uv run python .agents/skills/sailzen-ai-text-import/scripts/import_with_ai.py `
  "D:\ws\data\self\books\novel.txt" `
  --title "小说标题" `
  --author "作者名" `
  --preview  # 先预览

# 确认后正式导入
uv run python .agents/skills/sailzen-ai-text-import/scripts/import_with_ai.py `
  "D:\ws\data\self\books\novel.txt" `
  --title "小说标题" `
  --author "作者名" `
  --yes
```

### 数据库查询

```bash
uv run python -c "
import sys
sys.path.insert(0, '.')
from sail_server.utils.env import read_env
read_env('dev')
from sail_server.db import Database
from sail_server.data.text import Work

db = Database.get_instance().get_db_session()
works = db.query(Work).all()
for w in works:
    print(f'{w.id}: {w.title}')
"
```

## 参考资料

- [项目结构](references/project-structure.md) - 完整项目架构和技术栈
- [常用命令](references/common-commands.md) - uv/pnpm 命令速查
- [故障排除](references/troubleshooting.md) - 常见问题和解决方案

## 开发工作流

### 1. 启动开发服务器
```bash
# 终端 1: Python 后端
uv run server.py --dev

# 终端 2: 前端开发
pnpm run views:dev
```

### 2. 添加新依赖
```bash
# Python
uv add <package>

# Node.js
pnpm add <package>
```

### 3. 运行测试
```bash
# Python
uv run pytest

# TypeScript
pnpm test
```

### 4. 数据库操作
```bash
# 查询
uv run python -c "
from sail_server.utils.env import read_env
read_env('dev')
from sail_server.db import Database
db = Database.get_instance().get_db_session()
# ... 查询代码
"
```

## 重要提醒

1. **永远不要使用 `&&`** - PowerShell 使用 `;`
2. **总是使用 `uv run`** - 确保在正确的虚拟环境中
3. **设置环境变量** - 导入前检查 `$env:POSTGRE_URI`
4. **处理乱码** - 使用 `chcp 65001` 或忽略显示问题
5. **使用原始字符串** - 处理 Windows 路径时加 `r""` 前缀

## 快捷键

| 操作 | 命令 |
|------|------|
| 运行 Python | `uv run python script.py` |
| 进入 REPL | `uv run python` |
| 同步依赖 | `uv sync` |
| 安装包 | `uv add <pkg>` |
| 设置环境变量 | `$env:VAR="value"` |
| 修复编码 | `chcp 65001` |
| 命令分隔 | `cmd1; cmd2` |
