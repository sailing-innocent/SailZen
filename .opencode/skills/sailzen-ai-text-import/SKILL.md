---
name: sailzen-ai-text-import
description: AI驱动的智能文本导入工具，用于解析txt小说文件的章节结构。支持采样分析学习章节模式、智能识别特殊章节（楔子、番外等）、过滤广告噪音、异常章节检测，并提供人机确认界面。适用于各种非标准格式的小说文本导入。
---

# SailZen AI 文本导入 Skill

你是一个专业的小说文本导入 agent。核心工作流：**本地 AI 解析 → 构建干净中间结构 → 批量上传服务器**。

服务端不再负责解析，只负责稳定存储。解析逻辑全部在本地临时脚本中完成，每本书可以针对性调整。

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
import os

file_path = "books/novel.txt"
file_size = os.path.getsize(file_path)

with open(file_path, "rb") as f:
    raw = f.read(100000)

if raw.startswith(b'\xef\xbb\xbf'):
    encoding = 'utf-8-sig'
elif raw.startswith(b'\xff\xfe'):
    encoding = 'utf-16-le'
else:
    try:
        raw.decode('utf-8')
        encoding = 'utf-8'
    except UnicodeDecodeError:
        try:
            raw.decode('gb18030')
            encoding = 'gb18030'
        except UnicodeDecodeError:
            encoding = 'utf-8'

with open(file_path, "r", encoding=encoding, errors='replace') as f:
    text = f.read()

print(f"Size: {file_size:,} bytes | Encoding: {encoding} | Chars: {len(text):,}")
```

### Phase 2: 采样分析

从文本的**开头、中间、结尾**各采样 ~3000 字符，仔细阅读，识别：

1. **章节边界机制** — 文本用什么方式分隔章节？
   - 标题正则（`^第X章`、`^Chapter X`）
   - 分隔符行（`------------`、`===`、`***` 等）
   - 混合模式
2. **特殊章节** — 楔子、序章、番外、尾声？
3. **噪音内容** — 广告、URL、平台信息、作者感言？
4. **异常信号** — 章节编号是否跳跃？是否有多卷重置编号？

```python
sample_size = 3000
mid = len(text) // 2
for label, sample in [
    ("HEAD",   text[:sample_size]),
    ("MIDDLE", text[mid - sample_size//2 : mid + sample_size//2]),
    ("TAIL",   text[-sample_size:]),
]:
    print(f"\n{'='*60}\n  {label}\n{'='*60}")
    print(sample)
```

**阅读采样后，向用户说明：**
- 识别到的章节边界机制（正则 or 分隔符 or 其他）
- 特殊章节类型
- 预估章节数范围和平均字数

> ⚠️ **正则切分的陷阱**：如果文本章节标题存在变体（"第一章"/"第1章"/"第一章（第二更）"等），
> 单纯用标题正则会漏掉部分章节，导致相邻章节合并成超长章节。
> 每次识别到超长章节（>正常均值 3σ）都应检查是否切分失败。
> 如果文本有可靠的分隔符行（如 `------------`），**优先以分隔符为边界**，更稳定。

### Phase 3: 生成临时导入脚本

在工作目录生成 `_temp_import.py`，包含以下模块：

1. **文件读取 + 编码处理**
2. **章节切分**（根据采样结果选择策略）
3. **内容清洗**（每章内容单独清洗，不要清洗分隔符）
4. **章节分类**（standard / author / prologue / extra / epilogue）
5. **异常检测 + 分析报告**
6. **批量上传**（使用下方 Batch Upload API）

**完整脚本模板（重点是上传部分，解析部分根据每本书调整）：**

```python
import re
import os
import json
import urllib.request
import urllib.error
from typing import List, Tuple
from dataclasses import dataclass, field

FILE_PATH = "books/xxx.txt"
FILE_ENCODING = "utf-8"
WORK_TITLE = "小说标题"
WORK_AUTHOR = "作者名"
API_BASE = os.environ.get("SAILZEN_API_BASE", "http://localhost:4399/api/v1")
BATCH_SIZE = 100

AUTHOR_KEYWORDS = [
    "作者的话", "作者感言", "上架感言", "完本感言", "请假条",
    "求月票", "求保底月票", "三更", "六更", "七更", "更新已送",
    "总结兼", "申请休息", "暂停", "再请", "随便聊", "说几句",
    "说两个", "过年期间", "更新计划",
]
PROLOGUE_KEYWORDS = ["楔子", "序章", "序言", "引言", "引子"]
EPILOGUE_KEYWORDS = ["尾声", "后记", "终章", "完结篇", "大结局"]
EXTRA_KEYWORDS = ["番外", "外传", "特别篇"]

URL_PATTERN = re.compile(
    r'https?://[^\s<>"{}|\\^`\[\]]+'
    r'|www\.[^\s<>"{}|\\^`\[\]]+'
    r'|[a-zA-Z0-9.-]+\.(com|cn|net|org|io|cc|top|xyz)',
    re.IGNORECASE,
)
AD_LINE_PATTERNS = [
    re.compile(p) for p in [
        r"关注.*公众号", r"扫码.*加群", r"加入.*QQ群",
        r"关注.*微博", r"关注.*抖音", r"正版.*订阅",
        r"求推荐票", r"求收藏", r"求打赏", r"求订阅",
        r"投推荐票", r"投月票", r".*?群.*\d{5,}",
        r"本书.*首发于", r"版权所有.*盗版",
        r"VIP章节", r"付费章节",
    ]
]
GARBAGE_CHARS = set("锟斤拷烫屯臺")


@dataclass
class Chapter:
    index: int
    title: str
    label: str
    content_title: str
    chapter_type: str
    content: str
    char_count: int


def clean_content(content: str) -> str:
    lines = content.split("\n")
    cleaned = []
    for line in lines:
        if any(p.search(line.strip()) for p in AD_LINE_PATTERNS):
            continue
        cleaned.append(URL_PATTERN.sub("", line))
    result = []
    empty_count = 0
    for line in cleaned:
        if line.strip() == "":
            empty_count += 1
            if empty_count <= 2:
                result.append(line)
        else:
            empty_count = 0
            result.append(line)
    final = "\n".join(result).strip()
    for ch in GARBAGE_CHARS:
        final = final.replace(ch, "")
    return final


def classify_chapter(title: str) -> str:
    for kw in PROLOGUE_KEYWORDS:
        if kw in title:
            return "prologue"
    for kw in EPILOGUE_KEYWORDS:
        if kw in title:
            return "epilogue"
    for kw in EXTRA_KEYWORDS:
        if kw in title:
            return "extra"
    for kw in AUTHOR_KEYWORDS:
        if kw in title:
            return "author"
    return "standard"


def split_label_title(title: str) -> Tuple[str, str]:
    m = re.match(r"(第[一二三四五六七八九十百千万零〇\d]+章)\s*(.*)", title)
    if m:
        return m.group(1), m.group(2).strip()
    return title, ""


# ── 章节切分（根据采样结果替换此函数）──────────────────────────────────────
#
# 策略 A: 分隔符切分（适合有 ------------ 等分隔行的文本）
#   SEPARATOR_RE = re.compile(r"(?m)^-{3,}")
#   seps = [m.start() for m in SEPARATOR_RE.finditer(raw)]
#   segments between consecutive seps → each seg: first line = title, rest = content
#
# 策略 B: 标题正则切分（适合章节标题格式统一的文本）
#   regex = re.compile(r"^第[一二三四五六七八九十百千万零〇\d]+章[^\n]*", re.M)
#   matches → content between consecutive matches
#
# 混合策略: 先用正则找标题，若检测到超长章节（>avg+3σ），改用分隔符或人工审查
#
def parse_chapters(raw_text: str) -> List[Chapter]:
    raise NotImplementedError("根据采样结果实现此函数")


def detect_anomalies(chapters: List[Chapter]) -> List[str]:
    std = [c for c in chapters if c.chapter_type == "standard"]
    if len(std) < 3:
        return []
    lengths = [c.char_count for c in std]
    avg = sum(lengths) / len(lengths)
    variance = sum((x - avg) ** 2 for x in lengths) / len(lengths)
    std_dev = variance ** 0.5
    warnings = []
    for c in chapters:
        if c.char_count > avg + 3 * std_dev:
            warnings.append(f"[!] #{c.index} '{c.title}' 超长 ({c.char_count:,}, avg={avg:,.0f}) — 可能切分失败")
        elif c.char_count < 100:
            warnings.append(f"[!] #{c.index} '{c.title}' 极短 ({c.char_count})")
    return warnings


def print_report(chapters: List[Chapter], ad_lines_removed: int, warnings: List[str]):
    std = [c for c in chapters if c.chapter_type == "standard"]
    by_type: dict = {}
    for c in chapters:
        by_type[c.chapter_type] = by_type.get(c.chapter_type, 0) + 1
    total_chars = sum(c.char_count for c in chapters)
    avg_len = sum(c.char_count for c in std) / len(std) if std else 0

    print(f"\n{'='*60}")
    print(f"  {WORK_TITLE} / {WORK_AUTHOR}")
    print(f"  Segments: {len(chapters)}  Ad lines removed: {ad_lines_removed}")
    print(f"{'─'*60}")
    for t, cnt in sorted(by_type.items()):
        print(f"  {t:12s}: {cnt}")
    print(f"{'─'*60}")
    print(f"  Total chars: {total_chars:,}  Avg: {avg_len:,.0f}  "
          f"Min: {min(c.char_count for c in chapters):,}  Max: {max(c.char_count for c in chapters):,}")
    if warnings:
        print(f"{'─'*60}")
        for w in warnings:
            print(f"  {w}")
    print(f"\n{'='*60}  FIRST 3 STANDARD CHAPTERS")
    for c in [ch for ch in chapters if ch.chapter_type == "standard"][:3]:
        print(f"  [{c.index:4d}] {c.title[:50]}  ({c.char_count:,})")
        print(f"        {c.content[:70]}...")
    print(f"{'='*60}\n")


# ── Batch Upload (标准化，不随文本变化) ──────────────────────────────────────

def _http_post(url: str, payload: dict) -> dict:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode()[:300]}")


def _http_get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def upload_to_server(chapters: List[Chapter]) -> dict:
    upload_chapters = [
        c for c in chapters
        if c.chapter_type not in ("author", "noise", "other")
        and c.char_count >= 100
    ]
    total = len(upload_chapters)
    print(f"\n=== Upload: {total} chapters → {API_BASE} (batch={BATCH_SIZE}) ===")

    # Step 1: 创建 work + edition（空的，不含内容）
    print("Step 1: Create work + edition...")
    resp = _http_post(f"{API_BASE}/text/import/create", {
        "title": WORK_TITLE,
        "author": WORK_AUTHOR,
        "edition_name": "原始导入",
        "language": "zh",
    })
    work_id = resp["work"]["id"]
    edition_id = resp["edition"]["id"]
    print(f"  Work ID={work_id}  Edition ID={edition_id}")

    # Step 2: 分批上传已解析章节
    print(f"Step 2: Uploading {total} chapters in batches of {BATCH_SIZE}...")
    batches = [upload_chapters[i:i + BATCH_SIZE] for i in range(0, total, BATCH_SIZE)]
    for i, batch in enumerate(batches):
        start_index = i * BATCH_SIZE
        items = [
            {
                "label": c.label,
                "title": c.content_title,
                "content": c.content,
                "chapter_type": c.chapter_type,
                "meta_data": {},
            }
            for c in batch
        ]
        resp = _http_post(
            f"{API_BASE}/text/edition/{edition_id}/chapters/batch",
            {"chapters": items, "start_index": start_index},
        )
        print(f"  Batch {i+1}/{len(batches)}: accepted={resp['accepted']}  total_so_far={resp['total_chapters']}")

    # Step 3: 验证服务端章节数
    print("Step 3: Verify...")
    count_resp = _http_get(f"{API_BASE}/text/edition/{edition_id}/chapters/count")
    server_count = count_resp["count"]
    status = "✓ OK" if server_count == total else f"✗ MISMATCH (expected {total})"
    print(f"  Server count: {server_count}  {status}")

    return {"work_id": work_id, "edition_id": edition_id, "chapter_count": server_count}


def main():
    print(f"Reading {FILE_PATH} ({FILE_ENCODING})...")
    with open(FILE_PATH, "r", encoding=FILE_ENCODING, errors="replace") as f:
        raw_text = f.read()
    print(f"Raw: {len(raw_text):,} chars")

    chapters = parse_chapters(raw_text)
    warnings = detect_anomalies(chapters)
    print_report(chapters, 0, warnings)
    return chapters


if __name__ == "__main__":
    chapters = main()
    # upload_to_server(chapters)
```

### Phase 4: 用户确认

运行脚本后，展示分析报告，等待确认：

**必须确认的内容：**
1. 作品标题和作者是否正确
2. 总章节数是否合理（对比已知章节数）
3. 有无超长章节警告（> avg + 3σ）— **超长 = 切分失败信号**
4. author/noise 过滤数量是否合理

**超长章节的处理流程：**
```
检测到超长章节
  → 打印该段前500字，找到漏掉的边界
  → 分析为什么当前策略漏掉（标题格式变体？无标题？）
  → 调整 parse_chapters 策略后重新运行
  → 确认无超长章节后再上传
```

### Phase 5: 上传并验证

```python
result = upload_to_server(chapters)
```

上传完成后告知用户：
- Work ID、Edition ID
- 服务端验证章节数 vs 本地预期数（必须一致）
- 可在前端 `/text` 页面查看

## API 参考（当前服务端实现）

### 服务器地址

```
API_BASE = http://<host>:<port>/api/v1
默认端口: 4399
```

### Batch Import API（推荐，唯一支持大文件的方式）

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/text/import/create` | 创建空 work + edition |
| `POST` | `/text/edition/{id}/chapters/batch` | 批量写入已解析章节 |
| `GET`  | `/text/edition/{id}/chapters/count` | 验证章节数 |

#### Step 1: 创建 work + edition

```
POST /api/v1/text/import/create
```

Request:
```json
{
  "title": "作品标题",
  "author": "作者名",
  "edition_name": "原始导入",
  "language": "zh"
}
```

Response (200):
```json
{
  "work": {"id": 8, "slug": "诡秘之主", ...},
  "edition": {"id": 8, "work_id": 8, "edition_name": "原始导入", ...}
}
```

#### Step 2: 批量写入章节

```
POST /api/v1/text/edition/{edition_id}/chapters/batch
```

Request:
```json
{
  "chapters": [
    {
      "label": "第一章",
      "title": "绯红",
      "content": "章节正文...",
      "chapter_type": "standard",
      "meta_data": {}
    }
  ],
  "start_index": 0
}
```

- `label`: 章节编号部分（"第一章"、"Chapter 1"）
- `title`: 章节标题部分（"绯红"、"The Beginning"），无标题时留空串
- `start_index`: 本批次第一章的全局序号（用于续传/分批）
- 每批建议 **100 章**，单批 JSON 大小约 300-500KB，安全

Response (200):
```json
{
  "edition_id": 8,
  "accepted": 100,
  "total_chapters": 100
}
```

#### Step 3: 验证

```
GET /api/v1/text/edition/{edition_id}/chapters/count
```

Response:
```json
{"edition_id": 8, "count": 1411}
```

### 其他端点（仅供参考，不用于大文件导入）

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/text/import/` | 同步导入（仅适合小文件，有 body size 限制） |
| `POST` | `/text/import/append/{edition_id}` | 追加原始文本（服务端解析，不推荐） |
| `GET`  | `/text/work` | 列出所有作品 |
| `GET`  | `/text/work/{id}` | 获取作品详情 |

## 章节切分策略选择

**先观察文本结构，再选择策略，不要默认使用标题正则。**

| 文本特征 | 推荐策略 |
|----------|----------|
| 有一致的分隔符行（`---`、`===`等） | 以分隔符为边界，取第一行为标题 |
| 章节标题格式严格统一（无变体） | 标题正则切分 |
| 章节标题有多种变体（带更新说明等） | 分隔符优先，否则正则+手动修正 |
| 无明显章节标记 | 固定字数切分，或询问用户 |

**分隔符策略示例：**
```python
SEPARATOR_RE = re.compile(r"(?m)^-{3,}")
seps = [m.start() for m in SEPARATOR_RE.finditer(raw_text)]
for i in range(len(seps) - 1):
    seg_start = raw_text.find("\n", seps[i]) + 1
    seg_end = seps[i + 1]
    seg = raw_text[seg_start:seg_end].strip()
    title = seg.split("\n")[0].strip()
    content = "\n".join(seg.split("\n")[1:]).strip()
```

## 章节类型参考

| 类型 | 常见标题 | 默认处理 |
|------|----------|----------|
| `standard` | 第X章、Chapter X | 保留导入 |
| `prologue` | 楔子、序章、引言 | 保留导入 |
| `epilogue` | 尾声、后记、终章 | 保留导入 |
| `extra` | 番外、外传、特别篇 | 保留导入 |
| `author` | 感言、请假、求月票 | **过滤** |
| `noise` | 广告、平台信息 | **过滤** |

## 关键约束

1. **临时脚本命名**: 始终使用 `_temp_import.py`，导入完成后删除
2. **不使用 `requests` 库**: 使用标准库 `urllib.request`（服务器环境不一定有 requests）
3. **批量上传而非单次上传**: 大文件必须分批（每批 ~100 章），避免 413 错误
4. **上传前必须验证切分质量**: 超长章节（> avg + 3σ）是切分失败的信号，须修复后再上传
5. **用户确认**: 展示分析报告并获得用户确认后才执行上传
6. **编码处理**: 必须正确检测并使用源文件编码
7. **Windows 环境**: 脚本应使用 `python _temp_import.py` 或 `uv run python _temp_import.py` 运行

## 服务端模型参考

新增函数位于 `sail_server/model/text.py`：
- `create_work_with_edition_impl(db, title, author, edition_name, language)` → `(WorkResponse, EditionResponse)`
- `batch_insert_chapters_impl(db, edition_id, chapters: List[ChapterBatchItem], start_index)` → `int`
- `get_chapter_count_impl(db, edition_id)` → `int`
- `_make_slug(title, max_length)` — 内置 slug 生成（不依赖 slugify 库）

新增端点位于 `sail_server/controller/text.py`（`ImportController` + `EditionController`）：
- `POST /import/create` → `WorkEditionCreateResponse`
- `POST /edition/{id}/chapters/batch` → `ChapterBatchUploadResponse`
- `GET /edition/{id}/chapters/count` → `{"edition_id": int, "count": int}`

详细参考: [chapter_types.md](references/chapter_types.md) | [noise_patterns.md](references/noise_patterns.md)
