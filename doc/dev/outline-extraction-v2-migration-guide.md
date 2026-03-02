# 大纲提取 V2 升级指南

## 概述

本文档指导如何将大纲提取功能从 V1 升级到 V2。V2 版本引入了**位置锚点（Position Anchor）**机制，解决了以下问题：

1. 大纲节点保存后顺序与文本不一致
2. 长文本拆分并行处理后的合并顺序问题
3. 相同标题的大纲难以区分

## 主要改进

### 1. 位置锚点机制

V2 使用 `chapter_index`（章节全局索引）作为主要排序依据，而不是依赖 LLM 提供的 `sort_index`。

### 2. 两阶段保存策略

- 第一阶段：创建所有节点（不指定 parent_id），使用位置锚点确定 `sort_index`
- 第二阶段：更新 `parent_id` 关系

### 3. 增强的标题和描述

自动添加时间戳和更多信息，便于区分不同版本：
- 标题：`AI提取-主线-场景级 (2025-03-02 22:15)`
- 描述：`通过 LLM 自动提取的主线大纲 | 分析粒度：场景级 | 提取时间：2025-03-02 22:15:30 | 共 25 个节点`

## 升级步骤

### 步骤 1：确认文件准备就绪

确保以下文件已存在：

```
sail_server/
├── service/
│   ├── outline_extraction_v2.py      # V2 核心数据结构
│   ├── outline_extractor_v2.py       # V2 提取服务
│   └── outline_extractor.py          # V1 原始服务（保留）
└── model/analysis/
    ├── outline_v2.py                 # V2 数据库操作
    └── outline.py                    # V1 原始操作（保留）
```

### 步骤 2：修改控制器以支持 V2

编辑 `sail_server/controller/outline_extraction.py`，添加 V2 支持：

```python
# 在文件顶部添加 V2 导入
from sail_server.service.outline_extractor_v2 import OutlineExtractorV2
from sail_server.model.analysis.outline_v2 import OutlineBatchSaver

# 添加配置开关
USE_V2_EXTRACTOR = True  # 设置为 True 启用 V2，False 使用 V1
```

### 步骤 3：修改提取任务执行逻辑

在 `_run_extraction_task` 方法中，根据配置选择使用 V1 或 V2：

```python
async def _run_extraction_task(...):
    # ... 现有代码 ...
    
    with get_db_session() as db:
        try:
            if USE_V2_EXTRACTOR:
                # 使用 V2 提取器
                extractor = OutlineExtractorV2(db)
                result = await extractor.extract(...)
                # V2 返回的是 MergedOutlineResult，需要转换
                service_result = self._convert_v2_result(result)
            else:
                # 使用 V1 提取器
                extractor = OutlineExtractor(db)
                service_result = await extractor.extract(...)
            
            # ... 后续处理 ...
```

### 步骤 4：修改保存逻辑

在 `save_extraction_result` 方法中，根据配置选择使用 V1 或 V2：

```python
@post("/task/{task_id:str}/save")
async def save_extraction_result(...):
    # ... 前置检查 ...
    
    try:
        if USE_V2_EXTRACTOR:
            # 使用 V2 保存
            saver = OutlineBatchSaver(db)
            save_result = saver.save(
                edition_id=task["edition_id"],
                result=task["result"],  # 需要确保这是 MergedOutlineResult
                outline_type=task["config"]["outline_type"],
                granularity=task["config"]["granularity"],
            )
        else:
            # 使用 V1 保存
            extractor = OutlineExtractor(db)
            save_result = extractor.save_to_database(...)
        
        # ... 返回结果 ...
```

### 步骤 5：添加结果转换方法

在控制器中添加 V2 结果到 V1 格式的转换方法：

```python
def _convert_v2_result(self, v2_result: MergedOutlineResult) -> ServiceExtractionResult:
    """将 V2 结果转换为 V1 格式（用于兼容性）"""
    from sail_server.service.outline_extractor import ServiceExtractionResult, ExtractedTurningPoint
    from sail_server.application.dto.analysis import ExtractedOutlineNode, OutlineEvidence
    
    # 转换节点
    nodes = []
    for v2_node in v2_result.nodes:
        node = ExtractedOutlineNode(
            id=v2_node.id,
            node_type=v2_node.node_type,
            title=v2_node.title,
            summary=v2_node.summary,
            significance=v2_node.significance,
            sort_index=0,  # V2 中 sort_index 由位置锚点决定
            parent_id=v2_node.parent_id,
            characters=v2_node.characters,
            evidence_list=[
                OutlineEvidence(**ev) for ev in v2_node.evidence_list
            ],
        )
        nodes.append(node)
    
    # 转换转折点
    turning_points = [
        ExtractedTurningPoint(**tp) for tp in v2_result.turning_points
    ]
    
    return ServiceExtractionResult(
        nodes=nodes,
        turning_points=turning_points,
        metadata=v2_result.metadata,
    )
```

## 完整修改示例

以下是 `outline_extraction.py` 的完整修改示例：

```python
# -*- coding: utf-8 -*-
# ... 现有导入 ...

# ============================================================================
# V2 Support
# ============================================================================

# 配置开关：设置为 True 启用 V2，False 使用 V1
USE_V2_EXTRACTOR = True

if USE_V2_EXTRACTOR:
    from sail_server.service.outline_extractor_v2 import OutlineExtractorV2
    from sail_server.model.analysis.outline_v2 import OutlineBatchSaver
    from sail_server.service.outline_extraction_v2 import MergedOutlineResult

# ... 现有代码 ...

class OutlineExtractionController(Controller):
    # ... 现有代码 ...
    
    async def _run_extraction_task(self, ...):
        """运行提取任务（后台）- 支持 V1/V2 切换"""
        # ... 前置代码 ...
        
        with get_db_session() as db:
            try:
                if USE_V2_EXTRACTOR:
                    # ===== V2 提取流程 =====
                    logger.info(f"[Task {task_id}] Using V2 extractor")
                    extractor = OutlineExtractorV2(db)
                    
                    result = await extractor.extract(
                        edition_id=edition_id,
                        range_selection=range_selection,
                        config=config,
                        work_title=work_title,
                        known_characters=known_characters,
                        progress_callback=progress_callback,
                    )
                    
                    # 存储 V2 结果（MergedOutlineResult）
                    _complete_task_v2(task_id, result)
                    
                else:
                    # ===== V1 提取流程 =====
                    logger.info(f"[Task {task_id}] Using V1 extractor")
                    extractor = OutlineExtractor(db)
                    
                    result = await extractor.extract(
                        edition_id=edition_id,
                        range_selection=range_selection,
                        config=config,
                        work_title=work_title,
                        known_characters=known_characters,
                        progress_callback=progress_callback,
                        task_id=task_id,
                        resume_from_checkpoint=True,
                    )
                    
                    _complete_task(task_id, result)
                
                logger.info(f"[Task {task_id}] Task completed successfully")
                
            except Exception as e:
                logger.error(f"[Task {task_id}] Extraction failed: {e}")
                _fail_task(task_id, str(e))
    
    @post("/task/{task_id:str}/save")
    async def save_extraction_result(...):
        """保存提取结果 - 支持 V1/V2 切换"""
        # ... 前置检查 ...
        
        try:
            if USE_V2_EXTRACTOR and isinstance(task.get("result"), MergedOutlineResult):
                # ===== V2 保存流程 =====
                saver = OutlineBatchSaver(db)
                save_result = saver.save(
                    edition_id=task["edition_id"],
                    result=task["result"],
                    outline_type=task["config"]["outline_type"],
                    granularity=task["config"]["granularity"],
                )
            else:
                # ===== V1 保存流程 =====
                extractor = OutlineExtractor(db)
                save_result = extractor.save_to_database(
                    edition_id=task["edition_id"],
                    result=task["result"],
                    config=task["config"],
                )
            
            return {
                "success": True,
                "message": "大纲已保存到数据库",
                **save_result,
            }
            
        except Exception as e:
            raise ClientException(detail=f"Failed to save: {str(e)}")


# ============================================================================
# V2 Task Storage Helpers
# ============================================================================

def _complete_task_v2(task_id: str, result: MergedOutlineResult):
    """完成 V2 任务"""
    if task_id in _outline_extraction_tasks:
        task = _outline_extraction_tasks[task_id]
        task["status"] = "completed"
        task["phase"] = ExtractionPhase.COMPLETED.value
        task["progress"] = 100
        task["result"] = result
        task["completed_at"] = datetime.now()
        task["is_v2"] = True  # 标记为 V2 结果
        _save_task_state(task_id, task)
```

## 回滚方案

如果 V2 出现问题，可以快速回滚到 V1：

1. 修改 `USE_V2_EXTRACTOR = False`
2. 重启服务器

无需修改数据库，因为 V2 使用相同的表结构。

## 测试建议

升级后，建议进行以下测试：

1. **单章提取测试**
   - 选择单章文本进行提取
   - 验证节点顺序与原文一致

2. **多章提取测试**
   - 选择多章文本（超过 20 章）
   - 验证批次划分和合并是否正确

3. **长文本提取测试**
   - 选择整部作品进行提取
   - 验证并行处理和合并结果

4. **保存结果验证**
   - 检查标题是否包含时间戳
   - 检查描述是否包含节点数量
   - 验证数据库中的节点顺序

## 故障排查

### 问题 1：V2 提取结果顺序仍不正确

**检查点**：
- 确认 LLM 返回的 `position_anchor.chapter_index` 是否正确
- 检查批次划分是否正确传递了章节范围
- 查看合并日志，确认排序算法是否生效

**调试方法**：
```python
# 在合并后打印节点顺序
for i, node in enumerate(merged_result.nodes):
    print(f"{i}: {node.title} - anchor: {node.position_anchor}")
```

### 问题 2：保存时提示类型错误

**原因**：V1 和 V2 的结果类型不兼容

**解决**：确保在保存前正确识别结果类型：
```python
if isinstance(task.get("result"), MergedOutlineResult):
    # 使用 V2 保存
else:
    # 使用 V1 保存
```

### 问题 3：标题没有显示时间戳

**检查点**：
- 确认使用的是 V2 保存逻辑
- 检查 `OutlineBatchSaver.save()` 方法是否被调用

## 后续优化

V2 升级完成后，可以考虑以下优化：

1. **完全移除 V1 代码**
   - 在 V2 稳定运行一段时间后，可以移除 V1 相关代码

2. **添加更多元数据**
   - 提取参数详情
   - LLM 模型信息
   - 处理耗时统计

3. **支持真正的并行处理**
   - 当前 V2 是串行处理多批次
   - 可以改为使用 `asyncio.gather()` 并行处理

## 参考文档

- [大纲提取 V2 设计文档](../design/outline-extraction-parallel-merge.md)
- [大纲提取 V2 API 文档](../api/analysis.md)
