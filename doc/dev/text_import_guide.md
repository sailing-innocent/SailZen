# 文本导入工具使用指南

本文档介绍如何使用 SailZen 的文本导入工具将小说导入到系统中。

## 工具概述

`fix_chapter_import.py` - 智能章节导入修复工具，支持开发环境和生产环境导入。

## 基本用法

### 开发环境导入

```bash
# 基本导入（交互式确认）
uv run python scripts/fix_chapter_import.py "novel.txt" --title "作品标题" --author "作者名"

# 自动导入（跳过确认）
uv run python scripts/fix_chapter_import.py "novel.txt" --title "作品标题" --author "作者名" --yes
```

### 生产环境导入

```bash
# 生产环境导入（需要双重确认）
uv run python scripts/fix_chapter_import.py "novel.txt" --title "作品标题" --author "作者名" --prod
```

**⚠️ 警告**：生产环境导入会直接修改远程数据库，请谨慎操作！

## 生产环境安全机制

当使用 `--prod` 参数时，工具会启用以下安全机制：

### 1. 详细预览信息

导入前会显示以下信息供确认：
- 文件路径和作品信息
- 章节统计（总数、总字数、平均每章字数）
- 异常章节警告（超长/超短章节）
- 首尾章节预览

### 2. 双重确认流程

```
第一步：输入 'DEPLOY'（必须大写）
第二步：输入作品标题进行最终确认
```

### 3. 特殊选项

在确认界面，您还可以选择：
- 输入 `preview` - 仅预览，不导入
- 输入 `dev` - 切换到开发环境导入
- 输入其他内容 - 取消导入

### 4. --yes 参数限制

`--yes` 参数在生产环境下会被忽略，**必须进行手动确认**。

## 环境配置

### 开发环境 (.env.dev)

```
SERVER_PORT=4399
SERVER_HOST=localhost
POSTGRE_URI=postgresql://user:pass@localhost:5432/main
```

### 生产环境 (.env.prod)

```
SERVER_PORT=4399
SERVER_HOST=your-production-host
POSTGRE_URI=postgresql://user:pass@prod-host:5432/main
```

## 常见问题

### Q: 如何检查导入结果？

```bash
# 查看数据库中的作品
uv run python -c "
from sail_server.utils.env import read_env
read_env('dev')  # 或 'prod'
from sail_server.db import Database
db = Database.get_instance().get_db_session()
from sail_server.data.text import Work
works = db.query(Work).order_by(Work.id.desc()).limit(5).all()
for w in works:
    print(f'ID: {w.id}, 标题: {w.title}, 作者: {w.author}')
db.close()
"
```

### Q: 导入失败如何撤销？

```bash
# 使用 text_import_manager.py 撤销
uv run python scripts/text_import_manager.py --undo --work-id <作品ID>
```

### Q: 如何判断是否需要修复章节？

工具会自动检测并提示：
- **超长章节**：超过 50,000 字的章节，可能被合并了多个章节
- **超短章节**：少于 1,000 字的章节，可能是异常数据

## 最佳实践

1. **始终在开发环境先测试**：使用 `--prod` 前，先在开发环境验证导入结果
2. **检查章节数量**：网络小说通常 2000-5000 字/章，如果平均字数异常高，可能有合并问题
3. **备份数据**：生产环境导入前建议备份数据库
4. **使用 --yes 谨慎**：自动导入模式仅建议在开发环境使用

## 相关脚本

- `scripts/text_import_manager.py` - 导入管理工具（撤销、分析）
- `scripts/fix_chapter_import.py` - 智能导入修复工具（推荐）

## 故障排除

### 错误：无法解析文件编码

确保文件是 UTF-8 或 GBK 编码。如需转换：

```bash
# Linux/Mac
iconv -f GBK -t UTF-8 input.txt > output.txt

# Windows (PowerShell)
Get-Content input.txt -Encoding GB18030 | Set-Content output.txt -Encoding UTF8
```

### 错误：数据库连接失败

检查环境变量配置：
```bash
# 检查 .env 文件是否存在
cat .env.dev  # 开发环境
cat .env.prod  # 生产环境
```

### 错误：章节识别异常

如果章节数明显偏少，可能是：
1. 章节标题格式不标准（如缺少"第X章"）
2. 使用了特殊的章节标记（如"Chapter X"）

此时可以尝试修改脚本中的 `DEFAULT_CHAPTER_PATTERNS` 正则表达式。
