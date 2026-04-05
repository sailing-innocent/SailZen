# SailZen 故障排除指南

## 编码问题

### 问题：终端显示乱码（方块字符）
**症状**：输出显示为 `��` 或 `�T�T�T`

**原因**：Windows 控制台默认使用 GBK 编码，但程序输出 UTF-8

**解决方案**：
```powershell
# 临时设置当前会话
chcp 65001

# 或在脚本开头添加
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
```

**注意**：乱码通常是显示问题，数据本身是正常的。

### 问题：文件编码检测失败
**症状**：`UnicodeDecodeError` 或 `ValueError: 无法解析文件编码`

**解决方案**：
```python
# 使用 text_cleaner 中的 detect_encoding
from text_cleaner import detect_encoding
content, encoding = detect_encoding('file.txt')
print(f"Detected: {encoding}")
```

支持的编码：`utf-8`, `utf-8-sig`, `gb18030`, `gbk`, `gb2312`, `utf-16`, `big5`

## PowerShell 命令问题

### 问题：`&&` 不是有效的语句分隔符
**症状**：
```
The token '&&' is not a valid statement separator in this version.
```

**解决方案**：
```powershell
# ❌ 错误
cd dir && python script.py

# ✅ 正确 - 使用分号
cd dir; python script.py

# ✅ 正确 - 分两行
cd dir
python script.py

# ✅ 正确 - 使用管道
Get-Content file.txt | python script.py
```

### 问题：`head`, `tail`, `grep` 等命令不存在
**症状**：`CommandNotFoundException`

**解决方案**：
```powershell
# 使用 PowerShell 等效命令
# head -n 10
type file.txt | Select-Object -First 10

# tail -n 10
type file.txt | Select-Object -Last 10

# grep pattern
Select-String -Pattern "pattern" file.txt
# 或简写
type file.txt | Select-String "pattern"
```

### 问题：路径中的反斜杠被转义
**症状**：`OSError: [Errno 22] Invalid argument`

**解决方案**：
```python
# ❌ 错误 - Python 字符串中转义
path = "D:\path\to\file.txt"  # \t 变成制表符

# ✅ 正确 - 原始字符串
path = r"D:\path\to\file.txt"

# ✅ 正确 - 正斜杠
path = "D:/path/to/file.txt"

# ✅ 正确 - 双反斜杠
path = "D:\\path\\to\\file.txt"
```

## AI Agent 文件编辑教训

### 问题：edit 工具路径格式错误

**症状**：`File not found` 或 `oldString not found`

**错误示例**（在编辑 session_manager.py 时犯的错误）：
```python
# ❌ 错误 1: 路径格式错误（带冒号但缺少盘符）
":\\ws\\repos\\SailZen\\sail_bot\\session_manager.py"

# ❌ 错误 2: 路径重复
":\\ws\\repos\\SailZen\\:\\ws\\repos\\SailZen\\sail_bot\\session_manager.py"

# ❌ 错误 3: 盘符后使用正斜杠
"D:/ws/repos/SailZen/sail_bot/session_manager.py"

# ❌ 错误 4: 单斜杠（JSON 需要转义）
"D:\ws\repos\SailZen\sail_bot\session_manager.py"
```

**正确格式**：
```python
# ✅ Windows 绝对路径 - 双反斜杠
"D:\\ws\\repos\\SailZen\\sail_bot\\session_manager.py"

# ✅ 原始字符串（如果支持）
r"D:\ws\repos\SailZen\sail_bot\session_manager.py"
```

**验证路径**：
```powershell
Test-Path "D:\ws\repos\SailZen\sail_bot\session_manager.py"
```

**关键要点**：
1. Windows 路径必须使用双反斜杠 `\\`
2. 盘符后直接跟双反斜杠，如 `D:\\`
3. 不要使用 `:\\`（没有盘符）或混合斜杠
4. 编辑前先用 `Read` 工具确认文件内容和路径
5. 从 Read 工具的输出复制文件路径（已经包含正确的双反斜杠）

## Python/uv 问题

### 问题：`ModuleNotFoundError: No module named 'xxx'`
**症状**：导入 sail_server 或其他模块失败

**解决方案**：
```bash
# 1. 确保在项目根目录
cd D:\ws\repos\SailZen

# 2. 使用 uv run（自动使用 venv）
uv run python script.py

# 3. 确保路径正确
python -c "import sys; sys.path.insert(0, '.'); from sail_server import ..."
```

### 问题：`sqlalchemy.exc.ArgumentError: Expected string or URL object, got None`
**症状**：数据库 URI 为 None

**解决方案**：
```bash
# 1. 检查环境变量
$env:POSTGRE_URI

# 2. 设置环境变量
$env:POSTGRE_URI="postgresql://postgres:zzh666@localhost:5432/main"

# 3. 使用 read_env 加载
uv run python -c "
from sail.utils import read_env
read_env('dev')  # 或 'prod'
from sail_server.db import Database
db = Database.get_instance().get_db_session()
"
```

### 问题：uv sync 失败或卡住
**症状**：依赖同步失败

**解决方案**：
```bash
# 1. 检查网络连接
# 2. 清除缓存
uv cache clean

# 3. 重新同步
uv sync
```

## Node.js/pnpm 问题

### 问题：`ERR_PNPM_NO_MATCHING_VERSION`
**症状**：找不到匹配的包版本

**解决方案**：
```bash
# 1. 更新 pnpm
pnpm add -g pnpm

# 2. 删除 node_modules 并重新安装
Remove-Item -Recurse -Force node_modules
pnpm install
```

### 问题：构建失败，找不到模块
**症状**：`Cannot find module '@saili/xxx'`

**解决方案**：
```bash
# 按依赖顺序构建
pnpm run build:common-all
pnpm run build:common-server
pnpm run build:unified
pnpm run build:engine-server
# ... 以此类推

# 或构建全部
pnpm run build
```

## 数据库问题

### 问题：PostgreSQL 连接失败
**症状**：`Connection refused` 或 `FATAL: password authentication failed`

**解决方案**：
```bash
# 1. 检查 PostgreSQL 服务是否运行
Get-Service postgresql*

# 2. 检查连接字符串
# 格式: postgresql://user:password@host:port/database
$env:POSTGRE_URI="postgresql://postgres:your_password@localhost:5432/main"

# 3. 测试连接
psql -U postgres -d main -c "SELECT 1"
```

### 问题：`pg_client_encoding` 相关错误
**症状**：Windows 中文系统编码问题

**解决方案**：
```python
# sail_server/db.py 已设置
os.environ["PGCLIENTENCODING"] = "UTF8"
```

如需手动设置：
```powershell
$env:PGCLIENTENCODING="UTF8"
```

## AI/LLM 问题

### 问题：LLM API 调用失败
**症状**：API 返回错误或超时

**解决方案**：
```bash
# 1. 检查 API Key
$env:OPENAI_API_KEY
$env:GOOGLE_API_KEY
$env:MOONSHOT_API_KEY

# 2. 测试连接
uv run python -c "
from sail_server.utils.llm.client import LLMClient
client = LLMClient()
response = client.generate('Hello')
print(response)
"
```

### 问题：文本导入识别失败
**症状**：未识别到章节或识别错误

**解决方案**：
```bash
# 1. 使用预览模式检查
uv run python scripts/import_with_ai.py file.txt --preview

# 2. 使用规则模式（不使用 AI）
uv run python scripts/import_with_ai.py file.txt --no-ai --preview

# 3. 检查文本编码
file -i file.txt  # 或使用 Python 检测
```

## 通用调试技巧

### 查看完整错误堆栈
```powershell
# Python
$env:PYTHONTRACEMALLOC=1
uv run python script.py

# 或在代码中添加
import traceback
try:
    ...
except Exception as e:
    traceback.print_exc()
```

### 检查环境变量
```powershell
# 查看所有环境变量
Get-ChildItem Env:

# 查看特定变量
$env:POSTGRE_URI
$env:PATH

# 查看 Python 路径
uv run python -c "import sys; print('\n'.join(sys.path))"
```

### 检查文件编码
```powershell
# 使用 Python
uv run python -c "
with open('file.txt', 'rb') as f:
    raw = f.read(4)
    print(raw)
    # UTF-8 BOM: ef bb bf
    # UTF-16 LE: ff fe
"
```

## 快速修复检查清单

- [ ] 在项目根目录 (`D:|ws
epos|SailZen`) 运行命令
- [ ] 使用 `uv run` 运行 Python 代码
- [ ] 使用 `;` 而不是 `&&` 分隔 PowerShell 命令
- [ ] 设置 `$env:POSTGRE_URI`
- [ ] 使用 `chcp 65001` 修复显示乱码
- [ ] 路径使用原始字符串 `r"path"` 或正斜杠
- [ ] 导入前调用 `read_env('dev')`
