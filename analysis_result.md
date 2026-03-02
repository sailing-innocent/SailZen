# 大纲提取顺序问题分析与解决方案

## 问题现象

当前的大纲提取 `outline_extraction` 保存之后显示在页面上与文本顺序不一致。

## 根本原因分析

通过代码审查，发现以下关键问题：

### 1. 保存时忽略 LLM 提供的 sort_index（最主要原因）

**位置**: `sail_server/model/analysis/outline.py` 第 191-205 行

```python
# 获取同级节点的最大 sort_index
max_index = db.query(func.max(OutlineNode.sort_index)).filter(...).scalar() or -1
sort_index = max_index + 1
```

**问题**: `add_outline_node_impl` 函数**完全忽略**了传入节点的 `sort_index`，而是根据数据库中现有节点的最大索引自动计算新的 `sort_index`。

**后果**: 
- 父节点因为先被创建（排序键 `(n.parent_id is not None, n.sort_index)` 中父节点优先），总是获得较小的 `sort_index`
- 子节点后被创建，获得较大的 `sort_index`
- 即使原文本中子节点的内容先出现，保存后也会排在父节点之后

### 2. 父节点优先的排序策略破坏时间线

**位置**: `sail_server/service/outline_extractor.py` 第 913 行

```python
sorted_nodes = sorted(result.nodes, key=lambda n: (n.parent_id is not None, n.sort_index))
```

**问题**: 保存前排序时，父节点被强制排在子节点前面。

**后果**: 破坏了原文本的时间线顺序。

### 3. LLM 提供的 sort_index 本身不可靠

**问题**: 
- LLM 生成的 `sort_index` 只在单批次内有效
- 任务拆分后，各批次的 `sort_index` 可能冲突或重复
- 没有基于实际的文本位置

## 解决方案

设计了一套基于**位置锚点（Position Anchor）**的拆分-合并方案：

### 核心设计

1. **位置锚点机制**
   - 使用 `chapter_index`（章节全局索引）作为主要排序依据
   - 使用 `in_chapter_order`（章节内顺序）作为次要排序依据
   - 章节顺序是文本的固有属性，不受 LLM 输出影响

2. **两阶段保存策略**
   - 第一阶段：创建所有节点（不指定 parent_id），使用位置锚点确定 `sort_index`
   - 第二阶段：更新 `parent_id` 关系
   - 确保 `sort_index` 完全由位置决定，不受父子关系影响

3. **可靠的合并算法**
   - 基于位置锚点对所有批次的节点进行全局排序
   - 重新分配连续稳定的 ID
   - 智能推断跨批次的父子关系

### 实现文件

| 文件 | 说明 |
|------|------|
| `sail_server/service/outline_extraction_v2.py` | 核心数据结构和合并逻辑 |
| `sail_server/service/outline_extractor_v2.py` | V2 提取服务实现 |
| `sail_server/model/analysis/outline_v2.py` | V2 数据库操作（支持指定 sort_index） |
| `doc/design/outline-extraction-parallel-merge.md` | 详细设计文档 |

### 关键代码示例

**位置锚点定义**:
```python
class NodePositionAnchor(BaseModel):
    chapter_index: int      # 章节全局索引（主要排序依据）
    in_chapter_order: int   # 章节内顺序
    char_offset: Optional[int]  # 字符偏移量
```

**基于位置锚点的排序**:
```python
def _sort_by_position_anchor(self, nodes):
    def sort_key(node):
        anchor = node.get_effective_anchor()
        return (
            anchor.chapter_index,      # 主要：章节索引
            anchor.in_chapter_order,   # 次要：章节内顺序
            anchor.char_offset or 0,   # 第三：字符偏移
        )
    return sorted(nodes, key=sort_key)
```

**两阶段保存**:
```python
# 第一阶段：创建所有节点（不指定 parent_id）
for i, node in enumerate(sorted_nodes):
    add_outline_node_impl_v2(
        parent_id=None,
        specified_sort_index=i,  # 使用排序后的索引
        position_anchor=node.position_anchor,
    )

# 第二阶段：更新 parent_id
for node in sorted_nodes:
    if node.parent_id:
        update_node_parent(node.orm_id, parent_orm_id)
```

## 优势

1. **可靠性**: 基于章节位置的排序比 LLM 提供的 `sort_index` 更可靠
2. **可并行**: 各批次可以独立处理，合并时通过位置锚点排序
3. **向后兼容**: 保留现有接口，新功能通过新增字段实现
4. **降级能力**: 当 LLM 无法提供位置信息时，有可靠的降级策略

## 后续工作

1. 集成 V2 服务到现有提取流程
2. 添加单元测试和集成测试
3. 进行性能测试
4. 逐步替换 V1 实现
