# 大纲提取拆分-合并设计方案

## 问题背景

当前大纲提取存在以下问题：
1. LLM 提供的 `sort_index` 不可靠，特别是在任务拆分后
2. 保存时 `add_outline_node_impl` 忽略传入的 `sort_index`，自动重新计算
3. 父节点优先创建的策略破坏了原文本的时间线顺序

## 设计目标

1. **支持并行提取**：长文本可以拆分为多个批次并行处理
2. **保持顺序一致性**：合并后的节点顺序与原文本顺序一致
3. **保留层级结构**：正确处理父子节点关系
4. **可验证的顺序**：提供明确的排序依据，便于调试和验证

## 核心设计

### 1. 节点定位标识系统

引入**章节锚点（Chapter Anchor）**机制，用章节位置作为排序的可靠依据：

```python
class NodePositionAnchor(BaseModel):
    """节点位置锚点 - 用于确定节点在原文本中的顺序"""
    
    # 主要排序依据：节点首次出现的章节索引（0-based，全局）
    chapter_index: int = Field(description="节点首次出现的章节全局索引")
    
    # 次要排序依据：在章节内的顺序位置（0-based）
    in_chapter_order: int = Field(default=0, description="在章节内的出现顺序")
    
    # 可选：文本偏移量（字符数），用于精确定位
    char_offset: Optional[int] = Field(default=None, description="在章节内的字符偏移量")
    
    # 章节标题（用于验证和调试）
    chapter_title: Optional[str] = Field(default=None, description="章节标题")
    
    def to_sort_key(self) -> tuple:
        """生成排序键"""
        return (self.chapter_index, self.in_chapter_order, self.char_offset or 0)
```

**关键设计决策**：
- 使用 `chapter_index` 作为主要排序依据，因为章节顺序是文本的固有属性，不受 LLM 输出影响
- `chapter_index` 是**全局索引**（相对于整部作品），不是批次内的相对索引
- 批次处理时，通过提示词明确告知 LLM 当前批次的章节范围

### 2. 增强的节点数据结构

```python
class ExtractedOutlineNodeV2(BaseModel):
    """增强版提取的大纲节点"""
    
    # 原有字段
    id: str = Field(description="节点临时ID（批次内唯一）")
    node_type: str = Field(description="节点类型")
    title: str = Field(description="节点标题")
    summary: str = Field(description="节点摘要")
    significance: str = Field(description="重要性")
    parent_id: Optional[str] = Field(default=None, description="父节点临时ID")
    characters: List[str] = Field(default_factory=list)
    evidence_list: List[OutlineEvidence] = Field(default_factory=list)
    
    # 新增：位置锚点（核心排序依据）
    position_anchor: Optional[NodePositionAnchor] = Field(default=None)
    
    # 新增：层级深度（用于辅助排序和验证）
    depth: int = Field(default=0, description="节点深度")
    
    # 新增：批次信息（用于调试和追溯）
    batch_index: int = Field(default=0, description="所属批次索引")
```

### 3. 拆分策略

#### 3.1 基于章节的自然拆分

```python
class OutlineExtractionBatcher:
    """大纲提取批次划分器"""
    
    def __init__(
        self,
        max_chapters_per_batch: int = 20,
        max_tokens_per_batch: int = 8000,
        overlap_chapters: int = 1  # 批次间重叠章节数
    ):
        self.max_chapters = max_chapters_per_batch
        self.max_tokens = max_tokens_per_batch
        self.overlap = overlap_chapters
```

**设计要点**：
- 优先按章节边界拆分，保持章节完整性
- 批次间可以有 1 章重叠，用于保证跨批次边界的节点能被正确识别
- 记录每个批次的 `start_chapter_idx` 和 `end_chapter_idx`（全局索引）

#### 3.2 批次元数据传递

每个批次携带以下元数据：

```python
class ExtractionBatch(BaseModel):
    batch_index: int           # 批次序号
    start_chapter_idx: int     # 起始章节全局索引
    end_chapter_idx: int       # 结束章节全局索引
    chapter_ids: List[int]     # 章节ID列表
    estimated_tokens: int      # 预估token数
```

### 4. 提示词优化

V2 提示词的关键改进：

```yaml
### 位置锚点填写规则（重要）

**position_anchor** 字段用于确定节点在原文本中的位置：

1. **chapter_index** (必填):
   - 使用节点首次出现的章节的**全局索引**（从0开始）
   - 当前批次处理的章节全局索引范围是 {{start_chapter_idx}} 到 {{end_chapter_idx}}
   - 例如：如果节点首次出现在批次中的第2章，且批次起始索引是10，则填写11

2. **in_chapter_order** (必填):
   - 同一章节内多个节点的出现顺序（从0开始）
   - 按时间线顺序递增
```

### 5. 合并策略

#### 5.1 基于位置锚点的排序合并

```python
class OutlineMerger:
    def merge(self, batch_results: List[BatchExtractionResult]) -> MergedOutlineResult:
        # 1. 收集所有节点
        all_nodes = []
        for result in batch_results:
            all_nodes.extend(result.nodes)
        
        # 2. 基于位置锚点排序（核心步骤）
        sorted_nodes = self._sort_by_position_anchor(all_nodes)
        
        # 3. 重新分配连续ID
        id_mapping = self._reassign_ids(sorted_nodes)
        
        # 4. 更新父子关系
        self._update_parent_relationships(sorted_nodes, id_mapping)
        
        # 5. 冲突检测
        conflicts = self._detect_conflicts(sorted_nodes)
        
        return MergedOutlineResult(...)
```

**排序算法**：
```python
def _sort_by_position_anchor(self, nodes):
    def sort_key(node):
        anchor = node.get_effective_anchor()
        return (
            anchor.chapter_index,      # 主要：章节索引
            anchor.in_chapter_order,   # 次要：章节内顺序
            anchor.char_offset or 0,   # 第三：字符偏移
            node.depth,                # 第四：深度（父节点优先）
            node.title                 # 最后：标题稳定排序
        )
    return sorted(nodes, key=sort_key)
```

#### 5.2 父子关系处理

两阶段保存策略：

```python
class OutlineBatchSaver:
    def save(self, result: MergedOutlineResult):
        # 第一阶段：创建所有节点（不指定 parent_id）
        for i, node in enumerate(result.nodes):
            add_outline_node_impl_v2(
                parent_id=None,  # 暂不设置
                specified_sort_index=i,  # 使用排序后的索引
                position_anchor=node.position_anchor,
            )
        
        # 第二阶段：更新 parent_id
        for node in result.nodes:
            if node.parent_id:
                update_node_parent(node.orm_id, parent_orm_id)
```

**为什么这样设计**：
- 如果先创建父节点，父节点会获得较小的 `sort_index`
- 但父节点可能在文本中后于子节点出现
- 两阶段保存确保 `sort_index` 完全由位置锚点决定，不受父子关系影响

### 6. 冲突检测

```python
def _detect_conflicts(self, nodes: List[ExtractedOutlineNodeV2]) -> List[OutlineConflict]:
    conflicts = []
    
    # 1. 检测重复节点（相同位置相似内容）
    conflicts.extend(self._find_duplicates(nodes))
    
    # 2. 检测层级冲突（子节点出现在父节点之前）
    conflicts.extend(self._find_hierarchy_conflicts(nodes))
    
    # 3. 检测位置锚点异常
    conflicts.extend(self._find_anchor_anomalies(nodes))
    
    return conflicts
```

### 7. 降级策略

当 LLM 无法提供位置锚点时：

```python
def get_effective_anchor(self) -> NodePositionAnchor:
    """获取有效的位置锚点"""
    if self.position_anchor:
        return self.position_anchor
    
    # 降级：使用 batch_index 估计
    return NodePositionAnchor(
        chapter_index=self.batch_index * 1000,  # 假设每批最多1000章
        in_chapter_order=0,
        chapter_title=None
    )
```

## 实施计划

### 阶段 1：基础改造（已完成）
- [x] 添加 `NodePositionAnchor` 数据类
- [x] 修改 `ExtractedOutlineNodeV2` 添加位置锚点字段
- [x] 更新提示词模板，要求 LLM 提供位置信息

### 阶段 2：合并逻辑（已完成）
- [x] 实现 `OutlineMerger` 类
- [x] 实现冲突检测和解决逻辑
- [x] 添加降级策略

### 阶段 3：保存逻辑（已完成）
- [x] 修改 `add_outline_node_impl_v2` 支持指定 sort_index
- [x] 实现 `OutlineBatchSaver` 批量保存
- [x] 实现两阶段保存策略

### 阶段 4：集成与测试
- [ ] 集成到现有提取流程
- [ ] 添加单元测试
- [ ] 添加集成测试
- [ ] 性能测试

## 使用示例

### 基本使用

```python
from sail_server.service.outline_extractor_v2 import OutlineExtractorV2
from sail_server.model.analysis.outline_v2 import OutlineBatchSaver

# 创建提取器
extractor = OutlineExtractorV2(db)

# 执行提取
result = await extractor.extract(
    edition_id=1,
    range_selection=range_selection,
    config=config,
    work_title="示例小说",
)

# 保存结果
saver = OutlineBatchSaver(db)
save_result = saver.save(
    edition_id=1,
    result=result,
    outline_type="main",
    granularity="scene",
)
```

### 自定义批次配置

```python
from sail_server.service.outline_extraction_v2 import OutlineExtractionBatcher

# 自定义批次参数
batcher = OutlineExtractionBatcher(
    max_chapters_per_batch=10,  # 每批最多10章
    max_tokens_per_batch=6000,  # 每批最多6000 tokens
    overlap_chapters=2,          # 批次间重叠2章
)

extractor = OutlineExtractorV2(db)
extractor.batcher = batcher
```

### 验证结果

```python
from sail_server.service.outline_extraction_v2 import OutlineOrderValidator

validator = OutlineOrderValidator()
validation = validator.validate(result)

if not validation["valid"]:
    for issue in validation["issues"]:
        print(f"[{issue['severity']}] {issue['message']}")
```

## 关键优势

1. **可靠性**：基于章节位置（`chapter_index`）的排序比 LLM 提供的 `sort_index` 更可靠
2. **可并行**：各批次可以独立处理，合并时通过位置锚点排序
3. **可验证**：提供明确的排序依据，便于调试和验证
4. **向后兼容**：保留现有接口，新功能通过新增字段实现
5. **降级能力**：当 LLM 无法提供位置信息时，有可靠的降级策略

## 文件清单

| 文件 | 说明 |
|------|------|
| `sail_server/service/outline_extraction_v2.py` | 核心数据结构和合并逻辑 |
| `sail_server/service/outline_extractor_v2.py` | V2 提取服务 |
| `sail_server/model/analysis/outline_v2.py` | V2 数据库操作 |
| `doc/design/outline-extraction-parallel-merge.md` | 设计文档 |

## 迁移指南

### 从 V1 迁移到 V2

1. **代码层面**：
   ```python
   # V1
   from sail_server.service.outline_extractor import OutlineExtractor
   extractor = OutlineExtractor(db)
   result = await extractor.extract(...)
   
   # V2
   from sail_server.service.outline_extractor_v2 import OutlineExtractorV2
   extractor = OutlineExtractorV2(db)
   result = await extractor.extract(...)
   ```

2. **数据库层面**：
   - V2 使用相同的表结构
   - 位置锚点信息存储在 `meta_data` 字段中
   - 无需数据库迁移

3. **提示词层面**：
   - V2 使用新的提示词模板
   - 要求 LLM 提供 `position_anchor` 字段
