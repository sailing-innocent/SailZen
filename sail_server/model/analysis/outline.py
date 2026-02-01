# -*- coding: utf-8 -*-
# @file outline.py
# @brief Outline Management Business Logic
# @author sailing-innocent
# @date 2025-02-01
# ---------------------------------

from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func

from sail_server.data.analysis import (
    Outline, OutlineNode, OutlineEvent,
    OutlineData, OutlineNodeData, OutlineEventData,
    OutlineTree,
)


# ============================================================================
# Outline CRUD Operations
# ============================================================================

def create_outline_impl(db: Session, data: OutlineData) -> OutlineData:
    """创建大纲"""
    outline = data.create_orm()
    db.add(outline)
    db.commit()
    db.refresh(outline)
    return OutlineData.read_from_orm(outline)


def get_outline_impl(db: Session, outline_id: int) -> Optional[OutlineData]:
    """获取单个大纲"""
    outline = db.query(Outline).filter(Outline.id == outline_id).first()
    if not outline:
        return None
    
    node_count = db.query(func.count(OutlineNode.id)).filter(
        OutlineNode.outline_id == outline_id
    ).scalar() or 0
    
    return OutlineData.read_from_orm(outline, node_count)


def get_outlines_by_edition_impl(db: Session, edition_id: int) -> List[OutlineData]:
    """获取版本的所有大纲"""
    outlines = db.query(Outline).filter(
        Outline.edition_id == edition_id
    ).order_by(Outline.outline_type, Outline.created_at).all()
    
    result = []
    for outline in outlines:
        node_count = db.query(func.count(OutlineNode.id)).filter(
            OutlineNode.outline_id == outline.id
        ).scalar() or 0
        result.append(OutlineData.read_from_orm(outline, node_count))
    
    return result


def update_outline_impl(db: Session, outline_id: int, data: OutlineData) -> Optional[OutlineData]:
    """更新大纲"""
    outline = db.query(Outline).filter(Outline.id == outline_id).first()
    if not outline:
        return None
    
    data.update_orm(outline)
    db.commit()
    db.refresh(outline)
    return OutlineData.read_from_orm(outline)


def delete_outline_impl(db: Session, outline_id: int) -> bool:
    """删除大纲"""
    outline = db.query(Outline).filter(Outline.id == outline_id).first()
    if not outline:
        return False
    
    db.delete(outline)
    db.commit()
    return True


# ============================================================================
# Outline Node Operations
# ============================================================================

def add_outline_node_impl(
    db: Session,
    outline_id: int,
    node_type: str,
    title: str,
    parent_id: Optional[int] = None,
    summary: Optional[str] = None,
    significance: str = "normal",
    chapter_start_id: Optional[int] = None,
    chapter_end_id: Optional[int] = None,
    meta_data: Optional[Dict[str, Any]] = None
) -> Optional[OutlineNodeData]:
    """添加大纲节点"""
    outline = db.query(Outline).filter(Outline.id == outline_id).first()
    if not outline:
        return None
    
    # 计算 sort_index 和 depth
    if parent_id:
        parent = db.query(OutlineNode).filter(OutlineNode.id == parent_id).first()
        if not parent:
            return None
        
        depth = parent.depth + 1
        parent_path = parent.path
        
        # 获取同级节点的最大 sort_index
        max_index = db.query(func.max(OutlineNode.sort_index)).filter(
            OutlineNode.outline_id == outline_id,
            OutlineNode.parent_id == parent_id
        ).scalar() or -1
        sort_index = max_index + 1
    else:
        depth = 0
        parent_path = ""
        
        # 获取根节点的最大 sort_index
        max_index = db.query(func.max(OutlineNode.sort_index)).filter(
            OutlineNode.outline_id == outline_id,
            OutlineNode.parent_id.is_(None)
        ).scalar() or -1
        sort_index = max_index + 1
    
    # 生成 path
    if parent_path:
        path = f"{parent_path}.{sort_index:04d}"
    else:
        path = f"{sort_index:04d}"
    
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
        meta_data=meta_data or {},
    )
    db.add(node)
    db.commit()
    db.refresh(node)
    
    return OutlineNodeData.read_from_orm(node)


def get_outline_node_impl(db: Session, node_id: int) -> Optional[OutlineNodeData]:
    """获取单个大纲节点"""
    node = db.query(OutlineNode).filter(OutlineNode.id == node_id).first()
    if not node:
        return None
    
    children_count = db.query(func.count(OutlineNode.id)).filter(
        OutlineNode.parent_id == node_id
    ).scalar() or 0
    
    events_count = db.query(func.count(OutlineEvent.id)).filter(
        OutlineEvent.outline_node_id == node_id
    ).scalar() or 0
    
    return OutlineNodeData.read_from_orm(node, children_count, events_count)


def update_outline_node_impl(db: Session, node_id: int, data: OutlineNodeData) -> Optional[OutlineNodeData]:
    """更新大纲节点"""
    node = db.query(OutlineNode).filter(OutlineNode.id == node_id).first()
    if not node:
        return None
    
    # 只更新部分字段，不更新结构相关字段
    node.title = data.title
    node.summary = data.summary
    node.significance = data.significance
    node.chapter_start_id = data.chapter_start_id
    node.chapter_end_id = data.chapter_end_id
    node.status = data.status
    node.meta_data = data.meta_data
    
    db.commit()
    db.refresh(node)
    
    return OutlineNodeData.read_from_orm(node)


def delete_outline_node_impl(db: Session, node_id: int) -> bool:
    """删除大纲节点（包括子节点）"""
    node = db.query(OutlineNode).filter(OutlineNode.id == node_id).first()
    if not node:
        return False
    
    db.delete(node)
    db.commit()
    return True


def move_outline_node_impl(
    db: Session, 
    node_id: int, 
    new_parent_id: Optional[int],
    new_index: int
) -> bool:
    """移动大纲节点"""
    node = db.query(OutlineNode).filter(OutlineNode.id == node_id).first()
    if not node:
        return False
    
    outline_id = node.outline_id
    old_parent_id = node.parent_id
    
    # 计算新的 depth
    if new_parent_id:
        new_parent = db.query(OutlineNode).filter(OutlineNode.id == new_parent_id).first()
        if not new_parent:
            return False
        new_depth = new_parent.depth + 1
        new_parent_path = new_parent.path
    else:
        new_depth = 0
        new_parent_path = ""
    
    # 更新同级节点的 sort_index（在目标位置之后的节点后移）
    siblings = db.query(OutlineNode).filter(
        OutlineNode.outline_id == outline_id,
        OutlineNode.parent_id == new_parent_id if new_parent_id else OutlineNode.parent_id.is_(None),
        OutlineNode.id != node_id,
        OutlineNode.sort_index >= new_index
    ).all()
    
    for sibling in siblings:
        sibling.sort_index += 1
    
    # 更新节点
    node.parent_id = new_parent_id
    node.depth = new_depth
    node.sort_index = new_index
    
    # 更新 path
    if new_parent_path:
        node.path = f"{new_parent_path}.{new_index:04d}"
    else:
        node.path = f"{new_index:04d}"
    
    # 递归更新子节点的 depth 和 path
    _update_children_path(db, node)
    
    db.commit()
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


def get_outline_nodes_impl(db: Session, outline_id: int, parent_id: Optional[int] = None) -> List[OutlineNodeData]:
    """获取大纲的节点列表（按层级）"""
    query = db.query(OutlineNode).filter(OutlineNode.outline_id == outline_id)
    
    if parent_id is not None:
        query = query.filter(OutlineNode.parent_id == parent_id)
    else:
        query = query.filter(OutlineNode.parent_id.is_(None))
    
    nodes = query.order_by(OutlineNode.sort_index).all()
    
    result = []
    for node in nodes:
        children_count = db.query(func.count(OutlineNode.id)).filter(
            OutlineNode.parent_id == node.id
        ).scalar() or 0
        
        events_count = db.query(func.count(OutlineEvent.id)).filter(
            OutlineEvent.outline_node_id == node.id
        ).scalar() or 0
        
        result.append(OutlineNodeData.read_from_orm(node, children_count, events_count))
    
    return result


# ============================================================================
# Outline Tree Operations
# ============================================================================

def get_outline_tree_impl(db: Session, outline_id: int) -> Optional[OutlineTree]:
    """获取完整的大纲树结构"""
    outline = db.query(Outline).filter(Outline.id == outline_id).first()
    if not outline:
        return None
    
    # 获取所有节点
    all_nodes = db.query(OutlineNode).filter(
        OutlineNode.outline_id == outline_id
    ).order_by(OutlineNode.path).all()
    
    # 构建树形结构
    def build_tree(nodes: List[OutlineNode], parent_id: Optional[int] = None) -> List[Dict[str, Any]]:
        result = []
        for node in nodes:
            if node.parent_id == parent_id:
                events = db.query(OutlineEvent).filter(
                    OutlineEvent.outline_node_id == node.id
                ).order_by(OutlineEvent.chronology_order).all()
                
                node_dict = {
                    "id": node.id,
                    "node_type": node.node_type,
                    "title": node.title,
                    "summary": node.summary,
                    "significance": node.significance,
                    "chapter_start_id": node.chapter_start_id,
                    "chapter_end_id": node.chapter_end_id,
                    "path": node.path,
                    "depth": node.depth,
                    "sort_index": node.sort_index,
                    "status": node.status,
                    "events": [OutlineEventData.read_from_orm(e).__dict__ for e in events],
                    "children": build_tree(nodes, node.id),
                }
                result.append(node_dict)
        return result
    
    tree_nodes = build_tree(all_nodes)
    
    node_count = len(all_nodes)
    outline_data = OutlineData.read_from_orm(outline, node_count)
    
    return OutlineTree(outline=outline_data, nodes=tree_nodes)


# ============================================================================
# Outline Event Operations
# ============================================================================

def add_outline_event_impl(
    db: Session,
    node_id: int,
    event_type: str,
    title: str,
    description: Optional[str] = None,
    chronology_order: Optional[float] = None,
    narrative_order: Optional[int] = None,
    importance: str = "normal"
) -> Optional[OutlineEventData]:
    """添加大纲事件"""
    node = db.query(OutlineNode).filter(OutlineNode.id == node_id).first()
    if not node:
        return None
    
    event = OutlineEvent(
        outline_node_id=node_id,
        event_type=event_type,
        title=title,
        description=description,
        chronology_order=chronology_order,
        narrative_order=narrative_order,
        importance=importance,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    
    return OutlineEventData.read_from_orm(event)


def get_node_events_impl(db: Session, node_id: int) -> List[OutlineEventData]:
    """获取节点的事件列表"""
    events = db.query(OutlineEvent).filter(
        OutlineEvent.outline_node_id == node_id
    ).order_by(OutlineEvent.chronology_order).all()
    
    return [OutlineEventData.read_from_orm(e) for e in events]


def update_outline_event_impl(
    db: Session, 
    event_id: int,
    title: Optional[str] = None,
    description: Optional[str] = None,
    event_type: Optional[str] = None,
    chronology_order: Optional[float] = None,
    importance: Optional[str] = None
) -> Optional[OutlineEventData]:
    """更新大纲事件"""
    event = db.query(OutlineEvent).filter(OutlineEvent.id == event_id).first()
    if not event:
        return None
    
    if title is not None:
        event.title = title
    if description is not None:
        event.description = description
    if event_type is not None:
        event.event_type = event_type
    if chronology_order is not None:
        event.chronology_order = chronology_order
    if importance is not None:
        event.importance = importance
    
    db.commit()
    db.refresh(event)
    
    return OutlineEventData.read_from_orm(event)


def delete_outline_event_impl(db: Session, event_id: int) -> bool:
    """删除大纲事件"""
    event = db.query(OutlineEvent).filter(OutlineEvent.id == event_id).first()
    if not event:
        return False
    
    db.delete(event)
    db.commit()
    return True


# ============================================================================
# Link to Chapters
# ============================================================================

def link_node_to_chapters_impl(
    db: Session,
    node_id: int,
    start_chapter_id: int,
    end_chapter_id: Optional[int] = None
) -> bool:
    """将大纲节点链接到章节"""
    node = db.query(OutlineNode).filter(OutlineNode.id == node_id).first()
    if not node:
        return False
    
    node.chapter_start_id = start_chapter_id
    node.chapter_end_id = end_chapter_id or start_chapter_id
    
    db.commit()
    return True


def get_nodes_by_chapter_impl(db: Session, chapter_id: int) -> List[OutlineNodeData]:
    """获取与章节关联的大纲节点"""
    nodes = db.query(OutlineNode).filter(
        (OutlineNode.chapter_start_id <= chapter_id) &
        ((OutlineNode.chapter_end_id >= chapter_id) | (OutlineNode.chapter_end_id.is_(None)))
    ).order_by(OutlineNode.path).all()
    
    return [OutlineNodeData.read_from_orm(n) for n in nodes]
