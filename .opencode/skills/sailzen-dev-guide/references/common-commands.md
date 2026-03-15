# SailZen 常用开发命令

## Python 后端 (使用 uv)

### 安装依赖
```bash
# 同步依赖（根据 pyproject.toml 和 uv.lock）
uv sync

# 添加新依赖
uv add <package>

# 添加开发依赖
uv add --dev <package>
```

### 运行代码
```bash
# 运行服务器（必须使用 uv run）
uv run server.py

# 开发模式
uv run server.py --dev

# 运行任务
uv run main.py --task <task_name>

# 导入文本
uv run main.py --import-text <file.txt> --title "Title" --author "Author"
```

### 测试
```bash
# 运行所有测试
uv run pytest

# 运行特定测试
uv run pytest tests/server/test_finance.py

# 跳过异步测试
uv run pytest -m "not asyncio"
```

### Python 交互
```bash
# 进入 Python REPL（在项目环境中）
uv run python

# 执行单行代码
uv run python -c "print('hello')"

# 运行脚本
uv run python scripts/my_script.py
```

## TypeScript 前端 (使用 pnpm)

### 安装依赖
```bash
# 安装所有依赖
pnpm install

# 安装特定包
pnpm add <package>

# 安装开发依赖
pnpm add -D <package>
```

### 构建
```bash
# 构建所有包
pnpm run build

# 构建特定包及其依赖
pnpm run build-with-deps @saili/engine-server

# 构建插件
pnpm run build-plugin

# 构建站点
pnpm run build-site
```

### 开发
```bash
# 插件视图开发模式
pnpm run views:dev

# 构建插件视图
pnpm run views:build

# 复制视图到插件
pnpm run views:copy
```

### 测试
```bash
# 运行所有测试
pnpm test

# 运行特定包测试
pnpm run test:common-all

# 带覆盖率
pnpm run test:coverage
```

## 数据库操作

### 连接数据库
```bash
# 使用 psql
psql -U postgres -d main

# 或使用 uv run python
uv run python -c "
from sail_server.db import Database
from sail_server.utils.env import read_env
read_env('dev')
db = Database.get_instance().get_db_session()
print('Connected')
"
```

### 查询数据示例
```bash
uv run python -c "
from sail_server.db import Database
from sail_server.data.text import Work, Edition
from sail_server.utils.env import read_env
read_env('dev')

db = Database.get_instance().get_db_session()
works = db.query(Work).all()
for w in works:
    print(f'{w.id}: {w.title}')
"
```

## Windows PowerShell 注意事项

### 命令分隔符
```powershell
# ❌ 错误（Linux 风格）
cd dir && python script.py

# ✅ 正确（PowerShell 风格）
cd dir; python script.py

# 或分两行
cd dir
python script.py
```

### 环境变量
```powershell
# 临时设置（当前会话）
$env:POSTGRE_URI="postgresql://postgres:zzh666@localhost:5432/main"

# 验证
$env:POSTGRE_URI
```

### 路径处理
```powershell
# 使用原始字符串或转义
type file.txt                    # 简单文件
type "file with spaces.txt"      # 含空格
python "D:\path\to\file.py"      # 绝对路径
```

## 完整工作流示例

### 1. 开发新功能
```bash
# 1. 确保依赖最新
uv sync

# 2. 启动服务器（终端1）
uv run server.py --dev

# 3. 开发视图（终端2）
pnpm run views:dev

# 4. 运行测试
uv run pytest
pnpm test
```

### 2. 导入新小说
```bash
# 1. 确保环境变量
$env:POSTGRE_URI="postgresql://postgres:zzh666@localhost:5432/main"

# 2. 预览模式（AI skill）
uv run python .agents/skills/sailzen-ai-text-import/scripts/import_with_ai.py `
  "D:\ws\data\self\books\novel.txt" `
  --title "小说名" --author "作者" --preview

# 3. 正式导入
uv run python .agents/skills/sailzen-ai-text-import/scripts/import_with_ai.py `
  "D:\ws\data\self\books\novel.txt" `
  --title "小说名" --author "作者" --yes
```

### 3. 数据库调试
```bash
# 查询最新作品
uv run python -c "
import sys
sys.path.insert(0, '.')
from sail_server.db import Database
from sail_server.data.text import Work
from sail_server.utils.env import read_env
read_env('dev')
db = Database.get_instance().get_db_session()
work = db.query(Work).order_by(Work.id.desc()).first()
print(f'{work.id}: {work.title} ({work.author})')
"
```

## 快捷键速查

| 命令 | 作用 |
|------|------|
| `uv sync` | 同步 Python 依赖 |
| `uv run <cmd>` | 在 venv 中运行命令 |
| `pnpm install` | 安装 Node 依赖 |
| `pnpm run build` | 构建所有包 |
| `$env:VAR="value"` | 设置环境变量（PowerShell） |
| `cd dir; cmd` | 命令分隔（PowerShell） |
