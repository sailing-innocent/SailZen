---
name: sailzen-ai-text-import
description: AI驱动的智能文本导入工具，用于解析txt小说文件的章节结构。支持采样分析学习章节模式、智能识别特殊章节（楔子、番外等）、过滤广告噪音、异常章节检测，并提供人机确认界面。适用于各种非标准格式的小说文本导入。
---

# SailZen AI 文本导入 Skill

你是一个专业的小说文本导入 agent。给定一个 txt 小说文件，你需要：AI 采样识别其文本特征 → 撰写针对性的临时 Python 导入脚本 → 切分章节并清洗数据 → 通过 API 上传到远端服务器。

## 何时使用此 Skill

- 用户提供了一个 txt 格式的小说文件需要导入
- 需要从 `books/` 目录下选择文件导入
- 文件包含非标准章节格式（楔子、番外、作者感言等）
- 需要自动切分章节、清洗噪音、上传到 SailZen 后端

## 完整工作流程

### Phase 1: 文件探查

1. 确认文件路径和大小
2. 检测文件编码（UTF-8 / GBK / GB18030 / Big5 等）
3. 用正确编码读取文件，检查总字符数

```python
# 编码检测参考代码
import os

file_path = "books/novel.txt"
file_size = os.path.getsize(file_path)

# 读取原始字节检测编码
with open(file_path, "rb") as f:
    raw = f.read(100000)  # 前 100KB 足够检测

# 检查 BOM
if raw.startswith(b'\xef\xbb\xbf'):
    encoding = 'utf-8-sig'
elif raw.startswith(b'\xff\xfe'):
    encoding = 'utf-16-le'
else:
    # 尝试 UTF-8
    try:
        raw.decode('utf-8')
        encoding = 'utf-8'
    except UnicodeDecodeError:
        # 回退到 GBK/GB18030
        try:
            raw.decode('gb18030')
            encoding = 'gb18030'
        except UnicodeDecodeError:
            encoding = 'utf-8'  # 最后兜底

# 读取全文
with open(file_path, "r", encoding=encoding, errors='replace') as f:
    text = f.read()

print(f"File: {file_path}")
print(f"Size: {file_size:,} bytes")
print(f"Encoding: {encoding}")
print(f"Total chars: {len(text):,}")
```

### Phase 2: 采样分析

从文本的**开头、中间、结尾**各采样 ~3000 字符，仔细阅读样本内容，识别：

1. **章节标题模式** — 文本使用什么格式标记章节？
2. **特殊章节** — 是否有楔子、序章、番外、尾声？
3. **噪音内容** — 是否包含广告、URL、平台信息？
4. **文本特征** — 中文/英文？章节编号格式？有无内容标题？

```python
# 采样代码
sample_size = 3000
samples = []

# 开头
samples.append(("HEAD", text[:sample_size]))

# 中间
mid = len(text) // 2
samples.append(("MIDDLE", text[mid - sample_size//2 : mid + sample_size//2]))

# 结尾
samples.append(("TAIL", text[-sample_size:]))

for label, sample in samples:
    print(f"\n{'='*60}")
    print(f"  SAMPLE: {label}")
    print(f"{'='*60}")
    print(sample[:2000])
```

**阅读采样结果后，确定以下信息并告知用户：**

- 识别到的章节模式（如：`第X章 标题`、`Chapter X`）
- 特殊章节类型（如：楔子、番外）
- 是否存在需要清洗的噪音
- 预估总章节数范围

### Phase 3: 生成临时导入脚本

基于采样分析结果，在项目根目录下生成一个 **临时 Python 脚本** `_temp_import.py`。脚本必须：

1. 读取并解码文件
2. 清洗噪音内容（URL、广告、乱码等）
3. 使用针对性正则表达式切分章节
4. 识别并标记特殊章节类型
5. 检测异常章节（过长/过短）
6. 输出分析结果供用户确认
7. 用户确认后，通过 HTTP API 上传到服务器

**脚本模板结构：**

```python
# -*- coding: utf-8 -*-
# _temp_import.py - 临时导入脚本（由 AI 根据文本特征自动生成）
# 目标文件: books/xxx.txt
# 生成时间: YYYY-MM-DD HH:MM

import re
import os
import json
import requests
from typing import List, Tuple, Optional
from dataclasses import dataclass

# ============================================================================
# 配置区 - 根据采样分析结果填写
# ============================================================================

FILE_PATH = "books/xxx.txt"
FILE_ENCODING = "utf-8"  # 根据检测结果
WORK_TITLE = "小说标题"
WORK_AUTHOR = "作者名"

# 服务器配置
API_BASE = os.environ.get("SAILZEN_API_BASE", "http://localhost:4399/api/v1")

# 章节模式 - 根据采样分析结果定制
CHAPTER_PATTERNS = [
    r'^第[一二三四五六七八九十百千万零〇\d]+章[^\n]*',
]

# 特殊章节关键词
PROLOGUE_KEYWORDS = ["楔子", "序章", "序言", "引言", "开篇", "引子"]
EPILOGUE_KEYWORDS = ["尾声", "后记", "终章", "完结篇", "大结局"]
EXTRA_KEYWORDS = ["番外", "外传", "特别篇", "附录"]
AUTHOR_KEYWORDS = ["作者的话", "作者感言", "上架感言", "完本感言", "请假条"]


# ============================================================================
# 噪音清洗
# ============================================================================

# URL 模式
URL_PATTERN = re.compile(
    r'https?://[^\s<>"{}|\\^`\[\]]+'
    r'|www\.[^\s<>"{}|\\^`\[\]]+'
    r'|[a-zA-Z0-9.-]+\.(com|cn|net|org|io|cc|top|xyz)',
    re.IGNORECASE
)

# 广告关键词
AD_PATTERNS = [
    re.compile(p) for p in [
        r'关注.*公众号', r'扫码.*加群', r'加入.*QQ群',
        r'关注.*微博', r'关注.*抖音', r'正版.*订阅',
        r'感谢.*投票', r'求推荐', r'求收藏', r'求月票',
        r'求打赏', r'求订阅', r'投推荐票', r'投月票',
        r'.*?群.*\d{5,}',
    ]
]

# 平台信息
PLATFORM_PATTERNS = [
    re.compile(p) for p in [
        r'本书.*首发于', r'版权所有.*盗版', r'版权所有.*转载',
        r'VIP章节', r'付费章节',
    ]
]

# 乱码字符
GARBAGE_CHARS = set('锟斤拷烫屯臺')

# 纯符号行
SYMBOL_LINE_PATTERN = re.compile(r'^[\s\-=\*#~]{10,}$')


def clean_text(text: str) -> Tuple[str, dict]:
    """清洗文本，返回 (清洗后文本, 统计信息)"""
    stats = {"lines_removed": 0, "urls_removed": 0, "ads_removed": 0}
    lines = text.split('\n')
    cleaned = []

    for line in lines:
        # 跳过广告行
        if any(p.search(line) for p in AD_PATTERNS):
            stats["ads_removed"] += 1
            stats["lines_removed"] += 1
            continue

        # 跳过平台信息行
        if any(p.search(line) for p in PLATFORM_PATTERNS):
            stats["lines_removed"] += 1
            continue

        # 跳过纯符号行
        if SYMBOL_LINE_PATTERN.match(line.strip()):
            stats["lines_removed"] += 1
            continue

        # 移除行内 URL
        cleaned_line = URL_PATTERN.sub('', line)
        if cleaned_line != line:
            stats["urls_removed"] += 1

        cleaned.append(cleaned_line)

    # 合并连续空行（最多2个）
    result = []
    empty_count = 0
    for line in cleaned:
        if line.strip() == '':
            empty_count += 1
            if empty_count <= 2:
                result.append(line)
        else:
            empty_count = 0
            result.append(line)

    # 移除乱码字符
    final_text = '\n'.join(result)
    for char in GARBAGE_CHARS:
        final_text = final_text.replace(char, '')

    # 标准化换行
    final_text = final_text.replace('\r\n', '\n').replace('\r', '\n')

    return final_text, stats


# ============================================================================
# 章节切分
# ============================================================================

@dataclass
class Chapter:
    index: int
    title: str
    label: str           # 如"第一章"
    content_title: str   # 如"风云初起"
    chapter_type: str    # standard/prologue/epilogue/extra/author/noise
    content: str
    char_count: int


def classify_chapter(title: str) -> str:
    """根据标题识别章节类型"""
    title_lower = title.lower().strip()
    for kw in PROLOGUE_KEYWORDS:
        if kw in title_lower:
            return "prologue"
    for kw in EPILOGUE_KEYWORDS:
        if kw in title_lower:
            return "epilogue"
    for kw in EXTRA_KEYWORDS:
        if kw in title_lower:
            return "extra"
    for kw in AUTHOR_KEYWORDS:
        if kw in title_lower:
            return "author"
    return "standard"


def split_title(title: str) -> Tuple[str, str]:
    """拆分 '第一章 风云初起' -> ('第一章', '风云初起')"""
    # 根据采样分析结果定制这个函数
    match = re.match(r'(第[一二三四五六七八九十百千万零〇\d]+章)\s*(.*)', title)
    if match:
        return match.group(1), match.group(2)
    match = re.match(r'(Chapter\s+\d+)[:\s]*(.*)', title, re.IGNORECASE)
    if match:
        return match.group(1), match.group(2)
    return title, ""


def parse_chapters(text: str) -> List[Chapter]:
    """切分章节"""
    combined = '|'.join(f'({p})' for p in CHAPTER_PATTERNS)
    regex = re.compile(combined, re.MULTILINE | re.IGNORECASE)
    matches = list(regex.finditer(text))

    if not matches:
        return [Chapter(0, "正文", "", "正文", "standard", text.strip(), len(text))]

    chapters = []
    for i, match in enumerate(matches):
        title = match.group().strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[start:end].strip()

        label, content_title = split_title(title)
        chapter_type = classify_chapter(title)

        chapters.append(Chapter(
            index=i,
            title=title,
            label=label,
            content_title=content_title,
            chapter_type=chapter_type,
            content=content,
            char_count=len(content),
        ))

    return chapters


def detect_anomalies(chapters: List[Chapter]) -> List[str]:
    """检测异常章节"""
    if len(chapters) < 3:
        return []

    lengths = [c.char_count for c in chapters if c.chapter_type == "standard"]
    if not lengths:
        return []

    avg = sum(lengths) / len(lengths)
    std = (sum((x - avg) ** 2 for x in lengths) / len(lengths)) ** 0.5
    warnings = []

    for c in chapters:
        if c.char_count > avg + 3 * std:
            warnings.append(f"[!] Chapter {c.index} '{c.title}' is unusually long ({c.char_count:,} chars, avg={avg:,.0f})")
        if c.char_count < 100:
            warnings.append(f"[!] Chapter {c.index} '{c.title}' is very short ({c.char_count} chars)")

    return warnings


# ============================================================================
# 分析报告 & 确认
# ============================================================================

def print_report(chapters: List[Chapter], clean_stats: dict, warnings: List[str]):
    """打印分析报告"""
    std_chapters = [c for c in chapters if c.chapter_type == "standard"]
    special = {}
    for c in chapters:
        if c.chapter_type != "standard":
            special[c.chapter_type] = special.get(c.chapter_type, 0) + 1

    total_chars = sum(c.char_count for c in chapters)
    avg_len = sum(c.char_count for c in std_chapters) / len(std_chapters) if std_chapters else 0

    print(f"\n{'='*60}")
    print(f"  ANALYSIS REPORT")
    print(f"{'='*60}")
    print(f"  Title:       {WORK_TITLE}")
    print(f"  Author:      {WORK_AUTHOR}")
    print(f"  File:        {FILE_PATH}")
    print(f"  Encoding:    {FILE_ENCODING}")
    print(f"{'─'*60}")
    print(f"  Total chapters:  {len(chapters)}")
    print(f"  Standard:        {len(std_chapters)}")
    print(f"  Total chars:     {total_chars:,}")
    print(f"  Avg chapter:     {avg_len:,.0f} chars")
    if chapters:
        print(f"  Shortest:        {min(c.char_count for c in chapters):,} chars")
        print(f"  Longest:         {max(c.char_count for c in chapters):,} chars")
    print(f"{'─'*60}")

    if special:
        print(f"  Special chapters:")
        for t, count in special.items():
            print(f"    {t}: {count}")

    if clean_stats["lines_removed"] > 0:
        print(f"{'─'*60}")
        print(f"  Cleaning stats:")
        print(f"    Lines removed: {clean_stats['lines_removed']}")
        print(f"    URLs removed:  {clean_stats['urls_removed']}")
        print(f"    Ads removed:   {clean_stats['ads_removed']}")

    if warnings:
        print(f"{'─'*60}")
        print(f"  Warnings:")
        for w in warnings:
            print(f"    {w}")

    # 前3章预览
    print(f"\n{'='*60}")
    print(f"  FIRST 3 CHAPTERS PREVIEW")
    print(f"{'='*60}")
    for c in chapters[:3]:
        print(f"\n  [{c.index}] {c.title}  [{c.chapter_type.upper()}]")
        print(f"      Chars: {c.char_count:,}")
        print(f"      Start: {c.content[:80]}...")

    # 最后1章预览
    if len(chapters) > 3:
        c = chapters[-1]
        print(f"\n  [{c.index}] {c.title}  [{c.chapter_type.upper()}]")
        print(f"      Chars: {c.char_count:,}")
        print(f"      Start: {c.content[:80]}...")

    print(f"\n{'='*60}")


# ============================================================================
# 上传到服务器
# ============================================================================

def upload_to_server(chapters: List[Chapter]) -> dict:
    """
    通过 SailZen API 上传到服务器

    API: POST {API_BASE}/text/import/
    Body: {title, author, content, chapter_pattern}

    该 API 接受完整的文本内容和可选的章节匹配模式，
    服务端会自行解析章节。

    但我们已经做了更精确的切分，因此需要：
    1. 先创建作品和版本
    2. 逐章上传（或拼接后带自定义 pattern 上传）
    """
    # 方案1: 使用同步导入 API（简单，适合大多数情况）
    # 将已切分的章节重新拼接，用特殊标记分隔，让服务端再解析
    # 注意：如果 AI 切分更精确，优先使用方案2

    # 方案2: 先建作品，再逐章上传（精确控制）
    # Step 1: 拼接全文带标准章节标记
    rebuilt_content = ""
    for c in chapters:
        if c.chapter_type == "author":
            continue  # 跳过作者感言
        if c.chapter_type == "noise":
            continue  # 跳过噪音
        rebuilt_content += f"{c.title}\n{c.content}\n\n"

    # Step 2: 构建正则 - 使用我们已验证的模式
    pattern = '|'.join(CHAPTER_PATTERNS)

    # Step 3: 调用 API
    payload = {
        "title": WORK_TITLE,
        "author": WORK_AUTHOR,
        "content": rebuilt_content,
        "chapter_pattern": pattern,
    }

    print(f"\nUploading to {API_BASE}/text/import/ ...")
    resp = requests.post(f"{API_BASE}/text/import/", json=payload, timeout=120)

    if resp.status_code == 201:
        result = resp.json()
        print(f"Upload successful!")
        print(f"  Work ID:       {result.get('work', {}).get('id')}")
        print(f"  Edition ID:    {result.get('edition', {}).get('id')}")
        print(f"  Chapters:      {result.get('chapter_count')}")
        print(f"  Message:       {result.get('message')}")
        return result
    else:
        print(f"Upload FAILED: {resp.status_code}")
        print(f"  Response: {resp.text[:500]}")
        return {"error": resp.status_code, "detail": resp.text}


# ============================================================================
# Main
# ============================================================================

def main():
    print(f"Reading {FILE_PATH} with encoding {FILE_ENCODING}...")
    with open(FILE_PATH, "r", encoding=FILE_ENCODING, errors='replace') as f:
        raw_text = f.read()

    print(f"Raw text: {len(raw_text):,} chars")

    # 清洗
    print("Cleaning text...")
    cleaned_text, clean_stats = clean_text(raw_text)
    print(f"Cleaned text: {len(cleaned_text):,} chars")

    # 切分
    print("Parsing chapters...")
    chapters = parse_chapters(cleaned_text)

    # 检测异常
    warnings = detect_anomalies(chapters)

    # 报告
    print_report(chapters, clean_stats, warnings)

    # 过滤掉 author/noise 类型
    upload_chapters = [c for c in chapters if c.chapter_type not in ("author", "noise")]
    print(f"\nChapters to upload: {len(upload_chapters)} (filtered {len(chapters) - len(upload_chapters)} author/noise chapters)")

    return chapters, clean_stats, warnings


if __name__ == "__main__":
    chapters, clean_stats, warnings = main()
    # 上传部分需要用户确认后执行
    # upload_to_server(chapters)
```

### Phase 4: 用户确认

运行脚本后，向用户展示分析报告，等待确认：

**必须确认的内容：**
1. 作品标题和作者是否正确
2. 总章节数是否合理
3. 是否有被错误识别的章节
4. 异常章节是否需要处理
5. 被过滤的作者感言/噪音内容

**用户可能的指令：**
- "确认上传" / "OK" — 执行上传
- "第X章有问题" — 需要调整正则或手动处理
- "保留作者感言" — 修改过滤规则
- "合并第X和第Y章" — 手动合并
- "重新分析" — 调整正则后重新运行

### Phase 5: 上传到服务器

用户确认后，调用脚本中的 `upload_to_server()` 函数上传。

```python
# 在已运行的脚本环境中执行上传
upload_to_server(chapters)
```

上传完成后，告知用户：
- 作品 ID 和版本 ID
- 可在前端 `/text` 页面查看和审阅
- 如需追加章节，可使用追加 API

## API 参考

### 服务器地址

从环境变量获取，默认值参考 `.env.template`：
- `SERVER_HOST`: 默认 `0.0.0.0`
- `SERVER_PORT`: 默认 `4399`
- `API_ENDPOINT`: 默认 `/api/v1`

完整基础路径: `http://<host>:<port>/api/v1`

### 导入相关端点

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/text/import/` | 同步导入文本（推荐） |
| `POST` | `/text/import/append/{edition_id}` | 追加章节到已有版本 |
| `POST` | `/text/import-async/upload` | 上传文件（异步流程） |
| `POST` | `/text/import-async/` | 创建异步导入任务 |
| `GET`  | `/text/work` | 列出所有作品 |
| `GET`  | `/text/work/{id}` | 获取作品详情 |

### 同步导入 API 详情

**`POST /api/v1/text/import/`**

Request Body:
```json
{
  "title": "作品标题",
  "author": "作者名",
  "content": "完整文本内容（含章节标题）",
  "chapter_pattern": "可选，自定义章节正则表达式"
}
```

Response (201):
```json
{
  "work": {
    "id": 1,
    "slug": "zuo-pin-biao-ti",
    "title": "作品标题",
    "author": "作者名",
    "edition_count": 1,
    "chapter_count": 100,
    "total_chars": 500000
  },
  "edition": {
    "id": 1,
    "work_id": 1,
    "edition_name": "原始导入",
    "status": "active"
  },
  "chapter_count": 100,
  "message": "成功导入《作品标题》，共 100 章"
}
```

### 服务端章节解析逻辑

服务端 `import_text_impl` 会：
1. 创建 Work（作品）和 Edition（版本）
2. 使用 `chapter_pattern`（如果提供）或默认模式切分章节
3. 为每个章节创建 DocumentNode，包含 `label`、`title`、`raw_text`、`char_count`
4. 默认模式包括：`第X章`、`第X节`、`Chapter X`、`数字.标题`、`【标题】`

**因此，最佳策略是**：在脚本中完成精确的清洗和过滤，将处理后的干净文本（含原始章节标题）通过 API 上传，同时传入已验证的 `chapter_pattern` 正则让服务端完成最终切分。

## 章节类型参考

| 类型 | 标识 | 常见标题 | 默认处理 |
|------|------|----------|----------|
| 标准 | `standard` | 第X章、Chapter X | 保留导入 |
| 前置 | `prologue` | 楔子、序章、引言、开篇 | 保留导入 |
| 过渡 | `interlude` | 间章、插曲、幕间 | 保留导入 |
| 后置 | `epilogue` | 尾声、后记、终章、大结局 | 保留导入 |
| 番外 | `extra` | 番外、外传、特别篇 | 保留导入 |
| 作者 | `author` | 作者的话、感言、请假条 | **过滤** |
| 噪音 | `noise` | 广告、平台信息 | **过滤** |

详细参考: [chapter_types.md](references/chapter_types.md)

## 噪音清洗规则

**自动清理（高置信度）：**
- URL/链接: `https?://...`, `www.xxx.com`
- 纯符号行: 10个以上重复 `-=*#~` 字符
- 广告行: 含 "关注公众号"、"扫码加群"、"求推荐/月票" 等
- 乱码字符: `锟斤拷`、`烫烫烫` 等

**标记警告（需确认）：**
- 极短章节 (<200 字)
- 疑似重复的章节标题
- 章节序号跳跃（如第10章后直接第15章）

详细参考: [noise_patterns.md](references/noise_patterns.md)

## 异常检测

- **超长章节**: char_count > avg + 3*std — 可能包含未切分的多个章节
- **超短章节**: char_count < 100 — 可能是广告、作者说明或空章节
- **序号跳跃**: 章节编号不连续 — 可能遗漏了章节

## 关键约束

1. **临时脚本命名**: 始终使用 `_temp_import.py`，导入完成后删除
2. **编码处理**: 必须正确检测并使用源文件编码，不能简单假设 UTF-8
3. **用户确认**: 上传前**必须**向用户展示分析报告并获得确认
4. **噪音过滤**: 作者感言和噪音内容默认过滤，但允许用户选择保留
5. **服务器地址**: 从环境变量获取或询问用户，不要硬编码
6. **大文件**: 超过 10MB 的文件使用采样分析，不全文分析
7. **Windows 环境**: 脚本应使用 `uv run python _temp_import.py` 运行

## 参考资料

- [章节类型参考](references/chapter_types.md) — 完整的章节类型定义和处理规则
- [噪音模式参考](references/noise_patterns.md) — 常见广告和噪音内容的识别模式
- 服务端源码: `sail_server/utils/text_import/` — AI解析、清洗、编码检测实现
- 服务端控制器: `sail_server/controller/text.py` — ImportController
- 服务端模型: `sail_server/model/text.py` — `import_text_impl`, `parse_chapters`
