# -*- coding: utf-8 -*-
# @file outline_v2.py
# @brief Outline V2 Database Operations - Support for Position Anchor
# @author sailing-innocent
# @date 2025-03-02
# @version 1.0
# ---------------------------------

"""
大纲 V2 数据库操作

支持基于位置锚点的节点保存，保证节点顺序与原文本一致。
"""

from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func
import logging

logger = logging.getLogger(__name__)

from sail_server.infrastructure.orm.analysis import Outline, OutlineNode, OutlineEvent
from sail_server.application.dto.analysis import (
    OutlineResponse, OutlineCreateRequest,
    OutlineNodeResponse, OutlineNodeCreateRequest,
)


# ============================================================================
# Enhanced Node Creation with Position Anchor Support
# ============================================================================

def add_outline_node_impl_v2(
    db: Session,
    outline_id: int,
    node_type: str,
    title: str,
    parent_id: Optional[int] = None,
    summary: Optional[str] = None,
    significance: str = "normal",
    chapter_start_id: Optional[int] = None,
    chapter_end_id: Optional[int] = None,
    meta_data: Optional[Dict[str, Any]] = None,
    # V2 新增参数
    specified_sort_index: Optional[int] = None,
    position_anchor: Optional[Dict[str, Any]] = None,
) -> Optional[OutlineNodeResponse]:
    """
    添加大纲节点（V2 - 支持指定排序索引和位置锚点）
    
    与 V1 版本的关键区别：
    1. 允许通过 specified_sort_index 指定节点的排序位置
    2. 支持存储位置锚点信息到 meta_data
    3. 当指定 sort_index 时，会自动调整同级节点的索引以避免冲突
    
    Args:
        db: 数据库会话
        outline_id: 大纲ID
        node_type: 节点类型
        title: 标题
        parent_id: 父节点ID
        summary: 摘要
        significance: 重要性
        chapter_start_id: 起始章节ID
        chapter_end_id: 结束章节ID
        meta_data: 元数据
        specified_sort_index: 指定的排序索引（V2新增）
        position_anchor: 位置锚点信息（V2新增）
    
    Returns:
        创建的节点响应，失败返回 None
    """
    outline = db.query(Outline).filter(Outline.id == outline_id).first()
    if not outline:
        logger.error(f"Outline {outline_id} not found")
        return None
    
    # 计算 depth
    if parent_id:
        parent = db.query(OutlineNode).filter(OutlineNode.id == parent_id).first()
        if not parent:
            logger.error(f"Parent node {parent_id} not found")
            return None
        depth = parent.depth + 1
        parent_path = parent.path
    else:
        depth = 0
        parent_path = ""
    
    # 确定 sort_index
    if specified_sort_index is not None:
        # 使用指定的 sort_index，需要调整现有节点
        sort_index = specified_sort_index
        _shift_sibling_sort_indices(db, outline_id, parent_id, sort_index)
        logger.debug(f"Using specified sort_index {sort_index} for node '{title}'")
    else:
        # 自动计算（向后兼容）
        sort_index = _calculate_next_sort_index(db, outline_id, parent_id)
        logger.debug(f"Auto-calculated sort_index {sort_index} for node '{title}'")
    
    # 生成 path
    if parent_path:
        path = f"{parent_path}.{sort_index:04d}"
    else:
        path = f"{sort_index:04d}"
    
    # 合并元数据，包含位置锚点
    final_meta = dict(meta_data) if meta_data else {}
    if position_anchor:
        final_meta["position_anchor"] = position_anchor
        final_meta["extracted_with_v2"] = True
    
    node = OutlineNode(
        outline_id=outline_id,
        parent_id=parent_id,
        node_type=node_type,
        sort_index=sort_index,
        depth=depth,
        title=title,
        summary=summary,
        significance=significance,
        chapter_start_id=chapter_start_id,
        chapter_end_id=chapter_end_id,
        path=path,
        meta_data=final_meta,
    )
    db.add(node)
    db.commit()
    db.refresh(node)
    
    logger.info(f"Created outline node {node.id} '{title}' with sort_index {sort_index}")
    return _outline_node_to_response(node)


def _shift_sibling_sort_indices(
    db: Session,
    outline_id: int,
    parent_id: Optional[int],
    from_index: int
):
    """
    将同级节点中 sort_index >= from_index 的节点后移
    
    这是为了腾出位置给新插入的指定 sort_index 节点。
    从大到小处理，避免索引冲突。
    """
    query = db.query(OutlineNode).filter(
        OutlineNode.outline_id == outline_id,
        OutlineNode.sort_index >= from_index
    )
    
    if parent_id:
        query = query.filter(OutlineNode.parent_id == parent_id)
    else:
        query = query.filter(OutlineNode.parent_id.is_(None))
    
    # 从大到小排序，避免更新时冲突
    siblings = query.order_by(OutlineNode.sort_index.desc()).all()
    
    for sibling in siblings:
        old_index = sibling.sort_index
        sibling.sort_index = old_index + 1
        
        # 更新 path
        if sibling.parent_id:
            parent = db.query(OutlineNode).filter(OutlineNode.id == sibling.parent_id).first()
            if parent:
                sibling.path = f"{parent.path}.{sibling.sort_index:04d}"
        else:
            sibling.path = f"{sibling.sort_index:04d}"
        
        logger.debug(f"Shifted node {sibling.id} sort_index from {old_index} to {sibling.sort_index}")


def _calculate_next_sort_index(
    db: Session,
    outline_id: int,
    parent_id: Optional[int]
) -> int:
    """计算下一个可用的 sort_index"""
    query = db.query(func.max(OutlineNode.sort_index)).filter(
        OutlineNode.outline_id == outline_id
    )
    
    if parent_id:
        query = query.filter(OutlineNode.parent_id == parent_id)
    else:
        query = query.filter(OutlineNode.parent_id.is_(None))
    
    max_index = query.scalar()
    return (max_index or -1) + 1


def _outline_node_to_response(
    node: OutlineNode,
    children_count: int = 0,
    events_count: int = 0
) -> OutlineNodeResponse:
    """将 ORM 节点转换为响应 DTO"""
    return OutlineNodeResponse(
        id=node.id,
        outline_id=node.outline_id,
        title=node.title,
        node_type=node.node_type,
        summary=node.summary,
        significance=node.significance or "normal",
        parent_id=node.parent_id,
        depth=node.depth,
        path=node.path or "",
        sort_index=node.sort_index,
        chapter_start_id=node.chapter_start_id,
        chapter_end_id=node.chapter_end_id,
        status=node.status or "draft",
        created_at=node.created_at,
        updated_at=node.updated_at,
    )


def update_node_parent(
    db: Session,
    node_id: int,
    new_parent_id: Optional[int]
) -> bool:
    """
    更新节点的父节点
    
    用于批量保存的第二阶段：先创建所有节点，再建立父子关系。
    
    Args:
        db: 数据库会话
        node_id: 节点ID
        new_parent_id: 新的父节点ID
    
    Returns:
        是否成功
    """
    node = db.query(OutlineNode).filter(OutlineNode.id == node_id).first()
    if not node:
        return False
    
    # 计算新的 depth 和 path
    if new_parent_id:
        parent = db.query(OutlineNode).filter(OutlineNode.id == new_parent_id).first()
        if not parent:
            return False
        new_depth = parent.depth + 1
        new_path = f"{parent.path}.{node.sort_index:04d}"
    else:
        new_depth = 0
        new_path = f"{node.sort_index:04d}"
    
    node.parent_id = new_parent_id
    node.depth = new_depth
    node.path = new_path
    
    db.commit()
    
    # 递归更新子节点
    _update_children_path(db, node)
    
    logger.debug(f"Updated node {node_id} parent to {new_parent_id}, depth={new_depth}")
    return True


def _update_children_path(db: Session, parent_node: OutlineNode):
    """递归更新子节点的 depth 和 path"""
    children = db.query(OutlineNode).filter(
        OutlineNode.parent_id == parent_node.id
    ).all()
    
    for child in children:
        child.depth = parent_node.depth + 1
        child.path = f"{parent_node.path}.{child.sort_index:04d}"
        _update_children_path(db, child)
    
    if children:
        db.commit()


# ============================================================================
# Batch Save Operations
# ============================================================================

from sail_server.service.outline_extraction_v2 import (
    MergedOutlineResult,
    ExtractedOutlineNodeV2,
)


class OutlineBatchSaver:
    """
    大纲批量保存器
    
    实现两阶段保存策略：
    1. 先创建所有节点（不指定 parent_id），使用位置锚点确定 sort_index
    2. 然后更新 parent_id 关系
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def save(
        self,
        edition_id: int,
        result: MergedOutlineResult,
        outline_type: str = "main",
        granularity: str = "scene",
    ) -> Dict[str, Any]:
        """
        批量保存合并后的大纲结果
        
        Args:
            edition_id: 版本ID
            result: 合并后的大纲结果
            outline_type: 大纲类型
            granularity: 粒度
        
        Returns:
            保存结果统计
        """
        from sail_server.model.analysis.outline import create_outline_impl
        from sail_server.application.dto.analysis import OutlineData
        
        # 1. 创建大纲（添加时间戳和更多信息以便区分不同版本）
        from datetime import datetime
        now = datetime.now()
        timestamp = now.strftime("%Y-%m-%d %H:%M")
        
        # 构建更具描述性的标题
        type_labels = {
            "main": "主线",
            "subplot": "支线",
            "character_arc": "人物弧线",
            "theme": "主题",
        }
        type_label = type_labels.get(outline_type, outline_type)
        
        granularity_labels = {
            "act": "幕级",
            "arc": "弧级",
            "scene": "场景级",
            "beat": "节拍级",
        }
        granularity_label = granularity_labels.get(granularity, granularity)
        
        title = f"AI提取-{type_label}-{granularity_label} ({timestamp})"
        
        # 构建详细的描述信息
        description_parts = [
            f"通过 LLM 自动提取的{type_label}大纲",
            f"分析粒度：{granularity_label}",
            f"提取时间：{now.strftime('%Y-%m-%d %H:%M:%S')}",
            f"共 {len(result.nodes)} 个节点",
        ]
        
        if result.conflicts:
            description_parts.append(f"注意：合并过程中检测到 {len(result.conflicts)} 个冲突")
        
        outline_data = OutlineData(
            edition_id=edition_id,
            title=title,
            outline_type=outline_type,
            description=" | ".join(description_parts),
        )
        outline = create_outline_impl(self.db, outline_data)
        logger.info(f"Created outline {outline.id} for edition {edition_id}")
        
        # 2. 第一阶段：创建所有节点（不指定 parent_id）
        node_id_map: Dict[str, int] = {}  # temp_id -> orm_id
        
        for i, node in enumerate(result.nodes):
            # 使用位置排序后的索引作为 sort_index
            specified_sort_index = i
            
            # 提取位置锚点
            position_anchor = None
            if node.position_anchor:
                position_anchor = node.position_anchor.model_dump()
            
            node_data = add_outline_node_impl_v2(
                db=self.db,
                outline_id=outline.id,
                node_type=node.node_type,
                title=node.title,
                parent_id=None,  # 第一阶段不设置父节点
                summary=node.summary,
                significance=node.significance,
                specified_sort_index=specified_sort_index,
                position_anchor=position_anchor,
                meta_data={
                    "extracted": True,
                    "characters": node.characters,
                    "batch_index": node.batch_index,
                    "original_id": node.id,  # 保存原始ID用于追溯
                },
            )
            
            if node_data:
                node_id_map[node.id] = node_data.id
                logger.debug(f"Created node {node_data.id} from temp id {node.id}")
        
        logger.info(f"Phase 1 complete: Created {len(node_id_map)} nodes")
        
        # 3. 第二阶段：更新 parent_id
        parent_update_count = 0
        for node in result.nodes:
            if node.parent_id and node.id in node_id_map:
                orm_node_id = node_id_map[node.id]
                parent_orm_id = node_id_map.get(node.parent_id)
                
                if parent_orm_id:
                    success = update_node_parent(self.db, orm_node_id, parent_orm_id)
                    if success:
                        parent_update_count += 1
                else:
                    logger.warning(f"Parent node {node.parent_id} not found for node {node.id}")
        
        logger.info(f"Phase 2 complete: Updated {parent_update_count} parent relationships")
        
        # 4. 创建转折点事件
        event_count = 0
        for tp in result.turning_points:
            node_id = tp.get("node_id")
            if node_id and node_id in node_id_map:
                from sail_server.model.analysis.outline import add_outline_event_impl
                add_outline_event_impl(
                    db=self.db,
                    node_id=node_id_map[node_id],
                    event_type=tp.get("turning_point_type", "plot"),
                    title=tp.get("turning_point_type", "转折点"),
                    description=tp.get("description", ""),
                    importance="critical",
                )
                event_count += 1
        
        logger.info(f"Created {event_count} turning point events")
        
        return {
            "outline_id": outline.id,
            "nodes_created": len(node_id_map),
            "parent_relationships_updated": parent_update_count,
            "events_created": event_count,
            "conflicts": result.conflicts,
        }


# ============================================================================
# Export
# ============================================================================

__all__ = [
    "add_outline_node_impl_v2",
    "update_node_parent",
    "OutlineBatchSaver",
]
