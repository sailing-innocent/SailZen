# 大纲提取 V2 快速升级指南

## 概述

本文档提供大纲提取 V2 的快速升级步骤。V2 解决了节点顺序不一致的问题，并添加了时间戳区分功能。

## 已完成的修改

### 1. 新增文件（已创建）

```
sail_server/
├── service/
│   ├── outline_extraction_v2.py      # V2 核心数据结构 ✓
│   └── outline_extractor_v2.py       # V2 提取服务 ✓
└── model/analysis/
    └── outline_v2.py                 # V2 数据库操作 ✓

doc/
├── design/
│   └── outline-extraction-parallel-merge.md    # 设计文档 ✓
└── dev/
    └── outline-extraction-v2-migration-guide.md # 升级指南 ✓
```

### 2. 修改的文件（已完成）

- `sail_server/controller/outline_extraction.py` - 添加 V1/V2 切换支持
- `sail_server/service/outline_extractor.py` - 添加时间戳到标题和描述

## 升级步骤

### 步骤 1: 验证文件存在

确认以下文件已存在：

```bash
# 检查 V2 文件
ls -la sail_server/service/outline_extraction_v2.py
ls -la sail_server/service/outline_extractor_v2.py
ls -la sail_server/model/analysis/outline_v2.py
```

### 步骤 2: 配置切换开关

编辑 `sail_server/controller/outline_extraction.py`，确认 V2 已启用：

```python
# 第 41 行附近
USE_V2_EXTRACTOR = True  # 确保这是 True
```

### 步骤 3: 重启服务器

```bash
# 如果使用 uv
uv run server.py

# 或者
python server.py
```

### 步骤 4: 验证升级

1. **创建提取任务**
   ```bash
   curl -X POST http://localhost:8000/api/v1/analysis/outline-extraction/ \
     -H "Content-Type: application/json" \
     -d '{
       "edition_id": 1,
       "range_selection": {"mode": "full_edition", "edition_id": 1},
       "config": {"granularity": "scene", "outline_type": "main"}
     }'
   ```

2. **检查日志**
   - 应该看到 `[OutlineExtraction] V2 extractor loaded successfully`
   - 任务执行时应该看到 `[Task xxx] Using V2 extractor`

3. **保存后检查标题**
   - 标题格式应该为：`AI提取-主线-场景级 (2025-03-02 22:15)`
   - 描述应该包含提取时间和节点数量

## 回滚方案

如果 V2 出现问题，快速回滚到 V1：

1. 编辑 `sail_server/controller/outline_extraction.py`
2. 修改第 41 行：`USE_V2_EXTRACTOR = False`
3. 重启服务器

## 故障排查

### 问题 1: 导入错误

**症状**: 启动时提示 `ImportError: cannot import name 'OutlineExtractorV2'`

**解决**: 
```bash
# 检查文件是否存在
ls sail_server/service/outline_extractor_v2.py

# 如果存在，检查 Python 路径
cd sail_server
python -c "from service.outline_extractor_v2 import OutlineExtractorV2; print('OK')"
```

### 问题 2: 任务执行失败

**症状**: 任务状态变为 `failed`，日志显示 V2 相关错误

**解决**:
1. 查看详细错误日志
2. 临时切换回 V1 测试
3. 检查 LLM 返回的数据格式是否符合 V2 要求

### 问题 3: 保存失败

**症状**: 提取成功但保存时出错

**解决**:
1. 检查数据库连接
2. 查看 `outline_v2.py` 中的保存逻辑
3. 确认 `OutlineBatchSaver` 正确初始化

## 验证清单

升级后，请检查以下项目：

- [ ] 服务器启动无错误
- [ ] 创建提取任务成功
- [ ] 任务执行完成（状态为 `completed`）
- [ ] 保存结果成功
- [ ] 大纲标题包含时间戳
- [ ] 大纲描述包含节点数量
- [ ] 节点顺序与原文本一致

## 新功能说明

### 1. 增强的标题格式

**V1**: `自动提取 - main`

**V2**: `AI提取-主线-场景级 (2025-03-02 22:15)`

### 2. 增强的描述信息

**V1**: `通过 LLM 自动提取的大纲，粒度：scene`

**V2**: `通过 LLM 自动提取的主线大纲 | 分析粒度：场景级 | 提取时间：2025-03-02 22:15:30 | 共 25 个节点`

### 3. 可靠的节点顺序

V2 使用位置锚点机制确保节点顺序与原文本一致：
- 基于章节全局索引排序
- 两阶段保存策略（先创建节点，再建立父子关系）

## 性能考虑

V2 当前是串行处理多批次，如果需要并行处理：

```python
# 在 outline_extractor_v2.py 中修改
# 将串行处理改为并行
batch_results = await asyncio.gather(*[
    self._process_batch(batch, chapters, config, work_title, known_characters)
    for batch in batches
])
```

## 联系支持

如果遇到问题：
1. 查看详细日志
2. 参考 `doc/dev/outline-extraction-v2-migration-guide.md`
3. 检查 `doc/design/outline-extraction-parallel-merge.md` 了解设计细节
