# -*- coding: utf-8 -*-
# @file outline_extraction_v2.py
# @brief Outline Extraction V2 - Parallel Processing with Position Anchor
# @author sailing-innocent
# @date 2025-03-02
# @version 1.0
# ---------------------------------

"""
大纲提取 V2 - 支持并行处理和可靠顺序保证

核心特性：
1. 基于章节锚点的排序机制
2. 支持长文本拆分并行处理
3. 可靠的合并策略保证节点顺序
4. 冲突检测与降级策略
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from pydantic import BaseModel, Field
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# Data Models - Position Anchor System
# ============================================================================

class NodePositionAnchor(BaseModel):
    """
    节点位置锚点 - 用于确定节点在原文本中的顺序
    
    这是保证大纲节点顺序可靠性的核心机制。
    与 LLM 提供的 sort_index 不同，位置锚点基于实际的章节位置，
    在任务拆分后仍然能保持正确的排序。
    """
    
    # 主要排序依据：节点首次出现的章节索引（0-based，全局）
    chapter_index: int = Field(description="节点首次出现的章节全局索引")
    
    # 次要排序依据：在章节内的顺序位置（0-based）
    in_chapter_order: int = Field(default=0, description="在章节内的出现顺序")
    
    # 可选：文本偏移量（字符数），用于精确定位
    char_offset: Optional[int] = Field(default=None, description="在章节内的字符偏移量")
    
    # 章节标题（用于验证和调试）
    chapter_title: Optional[str] = Field(default=None, description="章节标题")
    
    def to_sort_key(self) -> Tuple[int, int, int]:
        """生成排序键，用于节点排序"""
        return (self.chapter_index, self.in_chapter_order, self.char_offset or 0)
    
    def __str__(self) -> str:
        return f"Anchor(ch{self.chapter_index}, order{self.in_chapter_order})"


class ExtractedOutlineNodeV2(BaseModel):
    """
    增强版提取的大纲节点
    
    相比 V1 版本，增加了位置锚点和批次信息，
    支持可靠的拆分-合并处理。
    """
    
    # 原有字段
    id: str = Field(description="节点临时ID（批次内唯一）")
    node_type: str = Field(description="节点类型: act/arc/scene/beat/turning_point")
    title: str = Field(description="节点标题")
    summary: str = Field(description="节点摘要")
    significance: str = Field(default="normal", description="重要性: critical/major/normal/minor")
    parent_id: Optional[str] = Field(default=None, description="父节点临时ID")
    characters: List[str] = Field(default_factory=list, description="涉及人物列表")
    evidence_list: List[Dict[str, Any]] = Field(default_factory=list, description="文本证据列表")
    
    # 新增：位置锚点（核心排序依据）
    position_anchor: Optional[NodePositionAnchor] = Field(default=None, description="位置锚点")
    
    # 新增：层级深度（用于辅助排序和验证）
    depth: int = Field(default=0, description="节点深度")
    
    # 新增：批次信息（用于调试和追溯）
    batch_index: int = Field(default=0, description="所属批次索引")
    
    def get_effective_anchor(self) -> NodePositionAnchor:
        """获取有效的位置锚点，如果没有则返回默认值"""
        if self.position_anchor:
            return self.position_anchor
        # 降级：使用 batch_index 作为章节索引的估计
        return NodePositionAnchor(
            chapter_index=self.batch_index * 1000,  # 假设每批最多1000章
            in_chapter_order=0,
            chapter_title=None
        )


class ExtractionBatch(BaseModel):
    """提取批次定义"""
    batch_index: int = Field(description="批次序号")
    start_chapter_idx: int = Field(description="起始章节全局索引")
    end_chapter_idx: int = Field(description="结束章节全局索引")
    chapter_ids: List[int] = Field(default_factory=list, description="章节ID列表")
    estimated_tokens: int = Field(default=0, description="预估token数")
    
    def to_prompt_context(self) -> str:
        """生成提示词中的批次上下文"""
        return f"""【批次信息】
- 这是第 {self.batch_index + 1} 个分析批次
- 包含章节：第 {self.start_chapter_idx + 1} 章 到 第 {self.end_chapter_idx + 1} 章
- 章节全局索引范围：{self.start_chapter_idx} - {self.end_chapter_idx}

【重要提示】
1. 请分析提供的章节内容，提取大纲节点
2. 每个节点的 position_anchor.chapter_index 必须是相对于全文章节索引的绝对值
3. 当前批次的章节索引范围是 {self.start_chapter_idx} 到 {self.end_chapter_idx}
4. 如果节点涉及跨章节内容，使用它首次出现的章节索引
"""


class BatchExtractionResult(BaseModel):
    """单个批次的提取结果"""
    batch_index: int = Field(description="批次序号")
    start_chapter_idx: int = Field(description="起始章节索引")
    end_chapter_idx: int = Field(description="结束章节索引")
    nodes: List[ExtractedOutlineNodeV2] = Field(default_factory=list, description="提取的节点")
    turning_points: List[Dict[str, Any]] = Field(default_factory=list, description="转折点")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")


class MergedOutlineResult(BaseModel):
    """合并后的大纲结果"""
    nodes: List[ExtractedOutlineNodeV2] = Field(default_factory=list, description="合并后的节点")
    turning_points: List[Dict[str, Any]] = Field(default_factory=list, description="转折点")
    conflicts: List[Dict[str, Any]] = Field(default_factory=list, description="检测到的冲突")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="合并元数据")


class OutlineConflict(BaseModel):
    """合并冲突"""
    conflict_type: str = Field(description="冲突类型: duplicate/hierarchy/boundary")
    severity: str = Field(description="严重程度: error/warning/info")
    node_ids: List[str] = Field(default_factory=list, description="涉及的节点ID")
    description: str = Field(description="冲突描述")
    suggestion: str = Field(default="", description="解决建议")


# ============================================================================
# Batch Planning
# ============================================================================

@dataclass
class ChapterInfo:
    """章节信息"""
    id: int
    sort_index: int
    title: Optional[str] = None
    label: Optional[str] = None
    char_count: int = 0
    content: str = ""


class OutlineExtractionBatcher:
    """
    大纲提取批次划分器
    
    负责将长文本划分为适合并行处理的批次，
    同时保留章节边界信息用于后续合并。
    """
    
    def __init__(
        self,
        max_chapters_per_batch: int = 20,
        max_tokens_per_batch: int = 8000,
        overlap_chapters: int = 1  # 批次间重叠章节数，用于保证连续性
    ):
        self.max_chapters = max_chapters_per_batch
        self.max_tokens = max_tokens_per_batch
        self.overlap = overlap_chapters
    
    def create_batches(self, chapters: List[ChapterInfo]) -> List[ExtractionBatch]:
        """
        创建提取批次
        
        策略：
        1. 优先按章节边界拆分，保持章节完整性
        2. 记录每个批次的章节范围，用于后续排序
        3. 批次间可以有重叠，保证跨批次边界的节点能被正确识别
        """
        if not chapters:
            return []
        
        batches = []
        current_start = 0
        
        while current_start < len(chapters):
            # 确定当前批次的结束位置
            current_end = min(current_start + self.max_chapters, len(chapters))
            
            # 计算当前批次的token数
            batch_chapters = chapters[current_start:current_end]
            total_tokens = sum(self._estimate_tokens(ch.content) for ch in batch_chapters)
            
            # 如果token超限，减少章节数
            while total_tokens > self.max_tokens and current_end > current_start + 1:
                current_end -= 1
                batch_chapters = chapters[current_start:current_end]
                total_tokens = sum(self._estimate_tokens(ch.content) for ch in batch_chapters)
            
            # 创建批次
            batch = ExtractionBatch(
                batch_index=len(batches),
                start_chapter_idx=batch_chapters[0].sort_index,
                end_chapter_idx=batch_chapters[-1].sort_index,
                chapter_ids=[ch.id for ch in batch_chapters],
                estimated_tokens=total_tokens
            )
            batches.append(batch)
            
            # 下一批次的起始位置（考虑重叠）
            current_start = current_end - self.overlap if current_end < len(chapters) else current_end
        
        logger.info(f"Created {len(batches)} batches for {len(chapters)} chapters")
        return batches
    
    def _estimate_tokens(self, text: str) -> int:
        """估算文本token数（中文约1.5字符/token）"""
        if not text:
            return 0
        return int(len(text) / 1.5)


# ============================================================================
# Merge Strategy
# ============================================================================

class OutlineMerger:
    """
    大纲合并器
    
    负责将多个批次的提取结果合并为一个有序的大纲，
    核心是基于位置锚点的排序算法。
    """
    
    def __init__(self, enable_conflict_detection: bool = True):
        self.enable_conflict_detection = enable_conflict_detection
    
    def merge(self, batch_results: List[BatchExtractionResult]) -> MergedOutlineResult:
        """
        合并多个批次的提取结果
        
        步骤：
        1. 收集所有节点
        2. 基于位置锚点排序
        3. 处理跨批次的父子关系
        4. 重新分配稳定ID
        5. 检测冲突
        """
        if not batch_results:
            return MergedOutlineResult()
        
        logger.info(f"Merging results from {len(batch_results)} batches")
        
        # 1. 收集所有节点
        all_nodes: List[ExtractedOutlineNodeV2] = []
        all_turning_points: List[Dict[str, Any]] = []
        
        for result in batch_results:
            for node in result.nodes:
                node.batch_index = result.batch_index
                all_nodes.append(node)
            all_turning_points.extend(result.turning_points)
        
        logger.info(f"Collected {len(all_nodes)} nodes from all batches")
        
        # 2. 基于位置锚点排序（核心步骤）
        sorted_nodes = self._sort_by_position_anchor(all_nodes)
        
        # 3. 重新分配连续ID
        id_mapping = self._reassign_ids(sorted_nodes)
        
        # 4. 更新父子关系
        self._update_parent_relationships(sorted_nodes, id_mapping)
        
        # 5. 更新转折点引用
        updated_turning_points = self._update_turning_points(all_turning_points, id_mapping)
        
        # 6. 冲突检测
        conflicts = []
        if self.enable_conflict_detection:
            conflicts = self._detect_conflicts(sorted_nodes)
            if conflicts:
                logger.warning(f"Detected {len(conflicts)} conflicts during merge")
        
        return MergedOutlineResult(
            nodes=sorted_nodes,
            turning_points=updated_turning_points,
            conflicts=[c.model_dump() for c in conflicts],
            metadata={
                "total_batches": len(batch_results),
                "total_nodes": len(sorted_nodes),
                "total_turning_points": len(updated_turning_points),
                "conflict_count": len(conflicts),
                "chapter_coverage": self._calculate_coverage(sorted_nodes)
            }
        )
    
    def _sort_by_position_anchor(
        self,
        nodes: List[ExtractedOutlineNodeV2]
    ) -> List[ExtractedOutlineNodeV2]:
        """
        基于位置锚点对节点排序
        
        排序优先级：
        1. chapter_index（章节索引）
        2. in_chapter_order（章节内顺序）
        3. char_offset（字符偏移量）
        4. depth（深度，同位置时父节点优先）
        """
        def sort_key(node: ExtractedOutlineNodeV2) -> Tuple:
            anchor = node.get_effective_anchor()
            return (
                anchor.chapter_index,
                anchor.in_chapter_order,
                anchor.char_offset or 0,
                node.depth,  # 同位置时，深度小的（父节点）优先
                node.title  # 最后按标题字母序作为稳定排序
            )
        
        return sorted(nodes, key=sort_key)
    
    def _reassign_ids(self, nodes: List[ExtractedOutlineNodeV2]) -> Dict[str, str]:
        """重新分配稳定ID"""
        id_mapping = {}
        for i, node in enumerate(nodes):
            old_id = node.id
            new_id = f"node_{i:04d}"
            id_mapping[old_id] = new_id
            node.id = new_id
        return id_mapping
    
    def _update_parent_relationships(
        self,
        nodes: List[ExtractedOutlineNodeV2],
        id_mapping: Dict[str, str]
    ):
        """更新父子关系"""
        # 创建ID到节点的映射
        node_map = {node.id: node for node in nodes}
        
        for node in nodes:
            if node.parent_id:
                if node.parent_id in id_mapping:
                    # 父节点在当前结果中
                    node.parent_id = id_mapping[node.parent_id]
                else:
                    # 父节点不在当前结果中，尝试推断
                    inferred_parent = self._infer_parent(node, nodes)
                    if inferred_parent:
                        node.parent_id = inferred_parent.id
                        node.depth = inferred_parent.depth + 1
                    else:
                        # 无法推断，设为根节点
                        node.parent_id = None
                        node.depth = 0
    
    def _infer_parent(
        self,
        node: ExtractedOutlineNodeV2,
        all_nodes: List[ExtractedOutlineNodeV2]
    ) -> Optional[ExtractedOutlineNodeV2]:
        """
        推断节点的父节点
        
        策略：
        1. 查找最近的祖先（chapter_index 小于等于当前节点）
        2. 优先匹配相同 chapter_index 的前序节点
        3. 考虑节点类型层级（act > arc > scene > beat）
        """
        if node.depth == 0:
            return None
        
        node_anchor = node.get_effective_anchor()
        node_chapter = node_anchor.chapter_index
        
        # 类型层级映射
        type_levels = {"act": 0, "arc": 1, "scene": 2, "beat": 3, "turning_point": 4}
        node_level = type_levels.get(node.node_type, 2)
        
        # 候选父节点：章节索引 <= 当前节点，且类型层级更高（数值更小）
        candidates = [
            n for n in all_nodes
            if n.id != node.id
            and n.get_effective_anchor().chapter_index <= node_chapter
            and type_levels.get(n.node_type, 2) < node_level
        ]
        
        if not candidates:
            return None
        
        # 排序：优先相同章节、深度接近、位置接近
        candidates.sort(key=lambda n: (
            abs(n.get_effective_anchor().chapter_index - node_chapter),
            -(n.depth),  # 深度大的优先（更接近当前节点）
            abs(n.get_effective_anchor().in_chapter_order - node_anchor.in_chapter_order)
        ))
        
        return candidates[0] if candidates else None
    
    def _update_turning_points(
        self,
        turning_points: List[Dict[str, Any]],
        id_mapping: Dict[str, str]
    ) -> List[Dict[str, Any]]:
        """更新转折点中的节点引用"""
        updated = []
        for tp in turning_points:
            old_node_id = tp.get("node_id")
            if old_node_id and old_node_id in id_mapping:
                new_tp = tp.copy()
                new_tp["node_id"] = id_mapping[old_node_id]
                updated.append(new_tp)
            else:
                updated.append(tp)
        return updated
    
    def _detect_conflicts(self, nodes: List[ExtractedOutlineNodeV2]) -> List[OutlineConflict]:
        """检测合并冲突"""
        conflicts = []
        
        # 1. 检测重复节点
        conflicts.extend(self._find_duplicates(nodes))
        
        # 2. 检测层级冲突
        conflicts.extend(self._find_hierarchy_conflicts(nodes))
        
        # 3. 检测位置锚点异常
        conflicts.extend(self._find_anchor_anomalies(nodes))
        
        return conflicts
    
    def _find_duplicates(self, nodes: List[ExtractedOutlineNodeV2]) -> List[OutlineConflict]:
        """查找重复节点"""
        conflicts = []
        
        # 按位置分组
        from collections import defaultdict
        position_groups: Dict[Tuple, List[ExtractedOutlineNodeV2]] = defaultdict(list)
        
        for node in nodes:
            key = node.get_effective_anchor().to_sort_key()
            position_groups[key].append(node)
        
        # 检测相似内容
        for key, group in position_groups.items():
            if len(group) > 1:
                for i, node1 in enumerate(group):
                    for node2 in group[i+1:]:
                        similarity = self._calculate_similarity(node1.title, node2.title)
                        if similarity > 0.8:
                            conflicts.append(OutlineConflict(
                                conflict_type="duplicate",
                                severity="warning",
                                node_ids=[node1.id, node2.id],
                                description=f"相似节点：'{node1.title}' 和 '{node2.title}' 在位置 {key}",
                                suggestion="建议检查是否为重复提取，考虑合并"
                            ))
        
        return conflicts
    
    def _find_hierarchy_conflicts(self, nodes: List[ExtractedOutlineNodeV2]) -> List[OutlineConflict]:
        """检测层级冲突"""
        conflicts = []
        node_map = {node.id: node for node in nodes}
        
        for node in nodes:
            if node.parent_id and node.parent_id in node_map:
                parent = node_map[node.parent_id]
                node_anchor = node.get_effective_anchor()
                parent_anchor = parent.get_effective_anchor()
                
                # 父节点不应该出现在子节点之后
                if parent_anchor.chapter_index > node_anchor.chapter_index:
                    conflicts.append(OutlineConflict(
                        conflict_type="hierarchy",
                        severity="warning",
                        node_ids=[node.id, parent.id],
                        description=f"父节点 '{parent.title}' 出现在子节点 '{node.title}' 之后",
                        suggestion="建议检查层级关系或调整位置锚点"
                    ))
        
        return conflicts
    
    def _find_anchor_anomalies(self, nodes: List[ExtractedOutlineNodeV2]) -> List[OutlineConflict]:
        """检测位置锚点异常"""
        conflicts = []
        
        for node in nodes:
            anchor = node.get_effective_anchor()
            
            # 检查是否有位置锚点
            if not node.position_anchor:
                conflicts.append(OutlineConflict(
                    conflict_type="boundary",
                    severity="info",
                    node_ids=[node.id],
                    description=f"节点 '{node.title}' 缺少位置锚点，使用批次索引估计",
                    suggestion="建议优化提示词以获取更精确的位置信息"
                ))
        
        return conflicts
    
    def _calculate_similarity(self, s1: str, s2: str) -> float:
        """计算字符串相似度（简单实现）"""
        if s1 == s2:
            return 1.0
        if not s1 or not s2:
            return 0.0
        
        # 使用简单的Jaccard相似度
        set1 = set(s1)
        set2 = set(s2)
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        return intersection / union if union > 0 else 0.0
    
    def _calculate_coverage(self, nodes: List[ExtractedOutlineNodeV2]) -> Dict[str, Any]:
        """计算章节覆盖情况"""
        if not nodes:
            return {}
        
        chapter_indices = [n.get_effective_anchor().chapter_index for n in nodes]
        return {
            "min_chapter": min(chapter_indices),
            "max_chapter": max(chapter_indices),
            "covered_chapters": len(set(chapter_indices))
        }


# ============================================================================
# Fallback Strategy
# ============================================================================

class PositionAnchorFallback:
    """
    位置锚点降级策略
    
    当 LLM 无法提供可靠的位置锚点时，使用证据信息推断位置。
    """
    
    def infer_from_evidence(
        self,
        node: ExtractedOutlineNodeV2,
        batch: ExtractionBatch
    ) -> NodePositionAnchor:
        """从证据推断位置锚点"""
        # 尝试从证据中提取章节信息
        for evidence in node.evidence_list:
            chapter_title = evidence.get("chapter_title")
            if chapter_title:
                # 在批次中查找匹配的章节
                # 这里假设 batch 有 chapter_titles 信息
                for i, ch_id in enumerate(batch.chapter_ids):
                    # 实际实现中需要从数据库查询章节标题
                    pass
        
        # 默认使用批次起始章节
        return NodePositionAnchor(
            chapter_index=batch.start_chapter_idx,
            in_chapter_order=0,
            chapter_title=f"Chapter {batch.start_chapter_idx + 1}"
        )


# ============================================================================
# Validation
# ============================================================================

class OutlineOrderValidator:
    """大纲顺序验证器"""
    
    def validate(self, result: MergedOutlineResult) -> Dict[str, Any]:
        """验证合并结果"""
        issues = []
        nodes = result.nodes
        
        if not nodes:
            return {"valid": True, "issues": []}
        
        # 1. 检查章节索引单调性
        chapter_indices = [n.get_effective_anchor().chapter_index for n in nodes]
        for i in range(1, len(chapter_indices)):
            if chapter_indices[i] < chapter_indices[i-1]:
                issues.append({
                    "type": "chapter_order",
                    "severity": "error",
                    "message": f"第 {i} 个节点的章节索引 ({chapter_indices[i]}) 小于前一个 ({chapter_indices[i-1]})"
                })
        
        # 2. 检查父子关系合理性
        node_map = {node.id: node for node in nodes}
        for node in nodes:
            if node.parent_id and node.parent_id in node_map:
                parent = node_map[node.parent_id]
                if parent.depth >= node.depth:
                    issues.append({
                        "type": "depth_inconsistency",
                        "severity": "warning",
                        "message": f"节点 '{node.title}' 的深度 ({node.depth}) 不大于父节点 '{parent.title}' ({parent.depth})"
                    })
        
        return {
            "valid": len([i for i in issues if i["severity"] == "error"]) == 0,
            "issues": issues
        }


# ============================================================================
# Export public API
# ============================================================================

__all__ = [
    "NodePositionAnchor",
    "ExtractedOutlineNodeV2",
    "ExtractionBatch",
    "BatchExtractionResult",
    "MergedOutlineResult",
    "OutlineConflict",
    "ChapterInfo",
    "OutlineExtractionBatcher",
    "OutlineMerger",
    "PositionAnchorFallback",
    "OutlineOrderValidator",
]
