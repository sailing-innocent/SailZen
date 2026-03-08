# -*- coding: utf-8 -*-
# @file result_merger.py
# @brief Result merging with deduplication
# @author sailing-innocent
# @date 2026-03-08
# @version 1.0
# ---------------------------------

"""结果合并器

合并不同层级的提取结果，处理：
- 结果去重
- 顺序保持
- 边界重叠处理
"""

from typing import List, Dict, Any, Set, Tuple
from difflib import SequenceMatcher
import logging

from .types import OutlineNode, Task, TaskLevel

logger = logging.getLogger(__name__)


class ChunkResultMerger:
    """Chunk 结果合并器

    将多个 chunk 的提取结果合并为一个 segment 的结果
    """

    def __init__(self, similarity_threshold: float = 0.85):
        self.similarity_threshold = similarity_threshold

    def merge(self, chunk_tasks: List[Task]) -> List[OutlineNode]:
        """合并 chunks 结果

        1. 按 chunk 索引排序
        2. 合并大纲节点列表
        3. 去重
        """
        # 按索引排序
        sorted_tasks = sorted(chunk_tasks, key=lambda t: t.index)

        # 收集所有节点
        all_nodes: List[OutlineNode] = []
        for task in sorted_tasks:
            if task.result and isinstance(task.result, list):
                all_nodes.extend(task.result)

        # 去重并排序
        merged = self._deduplicate_and_sort(all_nodes)

        logger.debug(f"Merged {len(all_nodes)} nodes into {len(merged)} unique nodes")

        return merged

    def _deduplicate_and_sort(self, nodes: List[OutlineNode]) -> List[OutlineNode]:
        """去重并排序"""
        if not nodes:
            return []

        # 按起始位置排序
        sorted_nodes = sorted(nodes, key=lambda n: n.start_pos)

        # 去重
        unique_nodes: List[OutlineNode] = []

        for node in sorted_nodes:
            is_duplicate = False

            for existing in unique_nodes:
                if self._is_duplicate(node, existing):
                    is_duplicate = True
                    # 合并元数据
                    existing.metadata.update(node.metadata)
                    break

            if not is_duplicate:
                unique_nodes.append(node)

        return unique_nodes

    def _is_duplicate(self, node1: OutlineNode, node2: OutlineNode) -> bool:
        """检查两个节点是否重复

        基于：
        1. 位置重叠
        2. 内容相似度
        """
        # 检查位置重叠
        pos_overlap = not (
            node1.end_pos <= node2.start_pos or node2.end_pos <= node1.start_pos
        )

        if not pos_overlap:
            return False

        # 检查内容相似度
        title_sim = SequenceMatcher(None, node1.title, node2.title).ratio()
        content_sim = SequenceMatcher(None, node1.content, node2.content).ratio()

        # 如果标题和内容都相似，认为是重复
        return (
            title_sim > self.similarity_threshold
            and content_sim > self.similarity_threshold
        )


class SegmentResultMerger:
    """Segment 结果合并器

    将多个 segment 的提取结果合并为 chapter 结果
    """

    def __init__(self, similarity_threshold: float = 0.85):
        self.similarity_threshold = similarity_threshold
        self.chunk_merger = ChunkResultMerger(similarity_threshold)

    def merge(self, segment_tasks: List[Task]) -> List[OutlineNode]:
        """合并 segments 结果

        1. 按 segment 索引排序
        2. 构建层级结构
        3. 合并相似节点
        """
        # 按索引排序
        sorted_tasks = sorted(segment_tasks, key=lambda t: t.index)

        # 收集所有节点
        all_nodes: List[OutlineNode] = []
        for task in sorted_tasks:
            if task.result and isinstance(task.result, list):
                # 添加 segment 上下文
                for node in task.result:
                    node.metadata["segment_index"] = task.index
                all_nodes.extend(task.result)

        # 构建层级树
        tree = self._build_tree(all_nodes)

        logger.debug(
            f"Built tree with {len(tree)} root nodes from {len(all_nodes)} total nodes"
        )

        return tree

    def _build_tree(self, nodes: List[OutlineNode]) -> List[OutlineNode]:
        """构建大纲树"""
        if not nodes:
            return []

        # 按起始位置排序
        sorted_nodes = sorted(nodes, key=lambda n: (n.start_pos, n.level))

        # 构建树
        root_nodes: List[OutlineNode] = []
        level_stack: List[OutlineNode] = []

        for node in sorted_nodes:
            # 去重检查
            is_duplicate = False
            for existing in root_nodes:
                if self._is_duplicate_in_tree(node, existing):
                    is_duplicate = True
                    break

            if is_duplicate:
                continue

            # 找到合适的父节点
            while level_stack and level_stack[-1].level >= node.level:
                level_stack.pop()

            if level_stack:
                # 作为子节点
                level_stack[-1].children.append(node)
            else:
                # 作为根节点
                root_nodes.append(node)

            level_stack.append(node)

        return root_nodes

    def _is_duplicate_in_tree(self, node: OutlineNode, tree_node: OutlineNode) -> bool:
        """在树中检查重复（递归）"""
        # 检查当前节点
        title_sim = SequenceMatcher(None, node.title, tree_node.title).ratio()
        content_sim = SequenceMatcher(None, node.content, tree_node.content).ratio()

        if (
            title_sim > self.similarity_threshold
            and content_sim > self.similarity_threshold
        ):
            return True

        # 递归检查子节点
        for child in tree_node.children:
            if self._is_duplicate_in_tree(node, child):
                return True

        return False

    def validate_order(self, nodes: List[OutlineNode]) -> bool:
        """验证节点顺序是否正确"""

        def check_order(node_list: List[OutlineNode], min_pos: int = 0) -> bool:
            for node in node_list:
                if node.start_pos < min_pos:
                    return False
                if node.children and not check_order(node.children, node.start_pos):
                    return False
                min_pos = node.end_pos
            return True

        return check_order(nodes)

    def format_as_outline(self, nodes: List[OutlineNode]) -> Dict[str, Any]:
        """格式化为标准大纲结构"""

        def node_to_dict(node: OutlineNode) -> Dict[str, Any]:
            return {
                "title": node.title,
                "content": node.content,
                "level": node.level,
                "position": {
                    "start": node.start_pos,
                    "end": node.end_pos,
                },
                "metadata": node.metadata,
                "children": [node_to_dict(child) for child in node.children],
            }

        return {
            "nodes": [node_to_dict(node) for node in nodes],
            "total_nodes": self._count_nodes(nodes),
        }

    def _count_nodes(self, nodes: List[OutlineNode]) -> int:
        """计算节点总数"""
        count = len(nodes)
        for node in nodes:
            count += self._count_nodes(node.children)
        return count
