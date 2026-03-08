# -*- coding: utf-8 -*-
# @file outline.py
# @brief Outline Management Controller
# @author sailing-innocent
# @date 2025-02-28
# @version 1.0
# ---------------------------------

from __future__ import annotations
from litestar import Controller, get, post, delete
from litestar.exceptions import NotFoundException, ClientException
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional, Generator
from dataclasses import dataclass, field

from sail_server.infrastructure.orm.analysis import (
    Outline,
    OutlineNode,
    OutlineEvent,
)
from sail_server.utils.pagination import (
    PaginationCursor,
    PaginatedResponse,
    create_paginated_response,
    parse_pagination_params,
)


# ============================================================================
# Response Models
# ============================================================================

@dataclass
class OutlineResponse:
    """大纲响应"""
    id: str
    edition_id: int
    title: str
    outline_type: str
    description: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass
class OutlineTreeResponse:
    """大纲树响应"""
    outline: OutlineResponse
    nodes: List[OutlineNodeResponse]


@dataclass
class OutlineNodeResponse:
    """大纲节点响应"""
    id: str
    outline_id: str
    parent_id: Optional[str]
    node_type: str
    title: str
    summary: Optional[str]
    sort_index: int
    children: List['OutlineNodeResponse'] = field(default_factory=list)
    events: List[Dict[str, Any]] = field(default_factory=list)
    created_at: Optional[str] = None


@dataclass
class CreateOutlineRequest:
    """创建大纲请求"""
    edition_id: int
    title: str
    outline_type: str
    description: Optional[str] = None


@dataclass
class CreateOutlineNodeRequest:
    """创建大纲节点请求"""
    outline_id: str
    parent_id: Optional[str]
    node_type: str
    title: str
    summary: Optional[str] = None
    sort_index: int = 0


@dataclass
class CreateOutlineEventRequest:
    """创建大纲事件请求"""
    node_id: str
    event_type: str
    description: str
    significance: Optional[str] = None


# ============================================================================
# Paginated Response Models (Performance Optimization)
# ============================================================================

@dataclass
class OutlineNodeListItem:
    """大纲节点列表项（精简版，用于分页）"""
    id: str
    outline_id: str
    parent_id: Optional[str]
    node_type: str
    title: str
    summary: Optional[str]
    significance: Optional[str]
    sort_index: int
    depth: int
    path: Optional[str]
    chapter_start_id: Optional[str] = None
    chapter_end_id: Optional[str] = None
    has_children: bool = False
    evidence_preview: Optional[str] = None
    evidence_full_available: bool = False
    events_count: int = 0


@dataclass
class PaginatedOutlineNodesResponse:
    """分页大纲节点响应"""
    nodes: List[OutlineNodeListItem]
    next_cursor: Optional[str]
    has_more: bool
    total_count: Optional[int] = None


@dataclass
class NodeEvidenceResponse:
    """节点证据响应"""
    node_id: str
    evidence_list: List[Dict[str, Any]]
    total_count: int


@dataclass
class NodeDetailResponse:
    """节点详情响应"""
    id: str
    outline_id: str
    parent_id: Optional[str]
    node_type: str
    title: str
    summary: Optional[str]
    significance: Optional[str]
    sort_index: int
    depth: int
    path: Optional[str]
    chapter_start_id: Optional[str] = None
    chapter_end_id: Optional[str] = None
    meta_data: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)
    child_count: int = 0


# ============================================================================
# Outline Controller
# ============================================================================

class OutlineController(Controller):
    """大纲管理控制器
    
    提供大纲的 CRUD 操作：
    - 获取版本的大纲列表
    - 创建/删除大纲
    - 获取大纲树结构
    - 添加/删除大纲节点
    - 添加大纲事件
    """
    path = "/outline"
    
    @get("/edition/{edition_id:int}")
    async def get_outlines_by_edition(
        self,
        edition_id: int,
        outline_type: Optional[str] = None,
        router_dependency: Generator[Session, None, None] = None,
    ) -> List[OutlineResponse]:
        """获取版本的大纲列表"""
        db = next(router_dependency)
        
        query = db.query(Outline).filter(Outline.edition_id == edition_id)
        
        if outline_type:
            query = query.filter(Outline.outline_type == outline_type)
        
        outlines = query.order_by(Outline.created_at.desc()).all()
        
        return [
            OutlineResponse(
                id=str(outline.id),
                edition_id=outline.edition_id,
                title=outline.title,
                outline_type=outline.outline_type,
                description=outline.description,
                created_at=outline.created_at.isoformat() if outline.created_at else None,
                updated_at=outline.updated_at.isoformat() if outline.updated_at else None,
            )
            for outline in outlines
        ]
    
    @post("/")
    async def create_outline(
        self,
        data: CreateOutlineRequest,
        router_dependency: Generator[Session, None, None] = None,
    ) -> OutlineResponse:
        """创建大纲"""
        db = next(router_dependency)
        
        try:
            outline = Outline(
                edition_id=data.edition_id,
                title=data.title,
                outline_type=data.outline_type,
                description=data.description,
            )
            
            db.add(outline)
            db.commit()
            db.refresh(outline)
            
            return OutlineResponse(
                id=str(outline.id),
                edition_id=outline.edition_id,
                title=outline.title,
                outline_type=outline.outline_type,
                description=outline.description,
                created_at=outline.created_at.isoformat() if outline.created_at else None,
                updated_at=outline.updated_at.isoformat() if outline.updated_at else None,
            )
            
        except Exception as e:
            db.rollback()
            raise ClientException(detail=f"Failed to create outline: {str(e)}")
    
    @delete("/{outline_id:str}", status_code=200)
    async def delete_outline(
        self,
        outline_id: str,
        router_dependency: Generator[Session, None, None] = None,
    ) -> Dict[str, Any]:
        """删除大纲"""
        db = next(router_dependency)
        
        try:
            outline = db.query(Outline).filter(Outline.id == int(outline_id)).first()
            
            if not outline:
                raise NotFoundException(detail=f"Outline {outline_id} not found")
            
            db.delete(outline)
            db.commit()
            
            return {"success": True, "message": "大纲已删除"}
            
        except Exception as e:
            db.rollback()
            raise ClientException(detail=f"Failed to delete outline: {str(e)}")
    
    @get("/{outline_id:str}/tree")
    async def get_outline_tree(
        self,
        outline_id: str,
        router_dependency: Generator[Session, None, None] = None,
    ) -> OutlineTreeResponse:
        """获取大纲树结构
        
        ⚠️ DEPRECATED: This endpoint loads the entire tree including all evidence text,
        which can cause performance issues with large outlines. 
        
        Please use the paginated `/nodes` endpoint instead for better performance.
        See: /doc/api/outline-paginated-api.md for migration guide.
        
        This endpoint will be removed in a future version.
        """
        db = next(router_dependency)
        
        outline = db.query(Outline).filter(Outline.id == int(outline_id)).first()
        
        if not outline:
            raise NotFoundException(detail=f"Outline {outline_id} not found")
        
        # 获取所有节点
        all_nodes = db.query(OutlineNode).filter(
            OutlineNode.outline_id == int(outline_id)
        ).order_by(OutlineNode.sort_index).all()
        
        # 获取所有事件
        all_events = db.query(OutlineEvent).filter(
            OutlineEvent.outline_node_id.in_([n.id for n in all_nodes])
        ).all()
        
        events_by_node = {}
        for event in all_events:
            if event.outline_node_id not in events_by_node:
                events_by_node[event.outline_node_id] = []
            events_by_node[event.outline_node_id].append({
                "id": str(event.id),
                "event_type": event.event_type,
                "title": event.title or "",
                "description": event.description,
            })
        
        # 构建树形结构
        def build_tree(nodes: List[OutlineNode], parent_id: Optional[int] = None) -> List[OutlineNodeResponse]:
            result = []
            for node in nodes:
                if node.parent_id == parent_id:
                    children = build_tree(nodes, node.id)
                    node_events = events_by_node.get(node.id, [])
                    
                    result.append(OutlineNodeResponse(
                        id=str(node.id),
                        outline_id=str(node.outline_id),
                        parent_id=str(node.parent_id) if node.parent_id else None,
                        node_type=node.node_type,
                        title=node.title,
                        summary=node.summary,
                        sort_index=node.sort_index,
                        children=children,
                        events=node_events,
                        created_at=node.created_at.isoformat() if node.created_at else None,
                    ))
            return result
        
        tree_nodes = build_tree(all_nodes)
        
        return OutlineTreeResponse(
            outline=OutlineResponse(
                id=str(outline.id),
                edition_id=str(outline.edition_id),
                title=outline.title,
                outline_type=outline.outline_type,
                description=outline.description,
                created_at=outline.created_at.isoformat() if outline.created_at else None,
                updated_at=outline.updated_at.isoformat() if outline.updated_at else None,
            ),
            nodes=tree_nodes,
        )
    
    @post("/node")
    async def add_outline_node(
        self,
        data: CreateOutlineNodeRequest,
        router_dependency: Generator[Session, None, None] = None,
    ) -> OutlineNodeResponse:
        """添加大纲节点"""
        db = next(router_dependency)
        
        try:
            node = OutlineNode(
                outline_id=int(data.outline_id),
                parent_id=int(data.parent_id) if data.parent_id else None,
                node_type=data.node_type,
                title=data.title,
                summary=data.summary,
                sort_index=data.sort_index,
            )
            
            db.add(node)
            db.commit()
            db.refresh(node)
            
            return OutlineNodeResponse(
                id=str(node.id),
                outline_id=str(node.outline_id),
                parent_id=str(node.parent_id) if node.parent_id else None,
                node_type=node.node_type,
                title=node.title,
                summary=node.summary,
                sort_index=node.sort_index,
                created_at=node.created_at.isoformat() if node.created_at else None,
            )
            
        except Exception as e:
            db.rollback()
            raise ClientException(detail=f"Failed to create node: {str(e)}")
    
    @delete("/node/{node_id:str}", status_code=200)
    async def delete_outline_node(
        self,
        node_id: str,
        router_dependency: Generator[Session, None, None] = None,
    ) -> Dict[str, Any]:
        """删除大纲节点"""
        db = next(router_dependency)
        
        try:
            node = db.query(OutlineNode).filter(OutlineNode.id == int(node_id)).first()
            
            if not node:
                raise NotFoundException(detail=f"Node {node_id} not found")
            
            db.delete(node)
            db.commit()
            
            return {"success": True, "message": "节点已删除"}
            
        except Exception as e:
            db.rollback()
            raise ClientException(detail=f"Failed to delete node: {str(e)}")
    
    @post("/event")
    async def add_outline_event(
        self,
        data: CreateOutlineEventRequest,
        router_dependency: Generator[Session, None, None] = None,
    ) -> Dict[str, Any]:
        """添加大纲事件"""
        db = next(router_dependency)
        
        try:
            event = OutlineEvent(
                outline_node_id=int(data.node_id),
                event_type=data.event_type,
                description=data.description,
                significance=data.significance,
            )
            
            db.add(event)
            db.commit()
            db.refresh(event)
            
            return {
                "success": True,
                "event_id": str(event.id),
                "message": "事件已添加",
            }
            
        except Exception as e:
            db.rollback()
            raise ClientException(detail=f"Failed to create event: {str(e)}")

    # ========================================================================
    # Paginated Endpoints (Performance Optimization)
    # ========================================================================

    @get("/{outline_id:str}/nodes")
    async def get_outline_nodes_paginated(
        self,
        outline_id: str,
        limit: int = 50,
        cursor: Optional[str] = None,
        parent_id: Optional[str] = None,
        router_dependency: Generator[Session, None, None] = None,
    ) -> PaginatedOutlineNodesResponse:
        """获取分页大纲节点列表
        
        Args:
            outline_id: 大纲ID
            limit: 每页数量 (1-100, 默认50)
            cursor: 分页游标
            parent_id: 父节点ID过滤 (可选)
        """
        db = next(router_dependency)
        
        # 解析分页参数
        try:
            pagination_cursor, validated_limit = parse_pagination_params(
                cursor_str=cursor,
                limit=limit,
                max_limit=100
            )
        except ValueError as e:
            raise ClientException(detail=f"Invalid pagination parameters: {str(e)}")
        
        # 验证大纲存在
        outline = db.query(Outline).filter(Outline.id == int(outline_id)).first()
        if not outline:
            raise NotFoundException(detail=f"Outline {outline_id} not found")
        
        # 构建基础查询
        query = db.query(OutlineNode).filter(
            OutlineNode.outline_id == int(outline_id)
        )
        
        # 应用父节点过滤
        if parent_id:
            query = query.filter(OutlineNode.parent_id == int(parent_id))
        else:
            query = query.filter(OutlineNode.parent_id.is_(None))
        
        # 应用游标过滤
        if pagination_cursor:
            from sqlalchemy import or_, and_
            query = query.filter(
                or_(
                    OutlineNode.sort_index > pagination_cursor.sort_index,
                    and_(
                        OutlineNode.sort_index == pagination_cursor.sort_index,
                        OutlineNode.id > pagination_cursor.node_id
                    )
                )
            )
        
        # 获取总数 (仅在第一页)
        total_count = None
        if not cursor:
            total_count = query.count()
        
        # 查询节点 (limit+1 用于判断是否有更多)
        nodes = query.order_by(
            OutlineNode.sort_index.asc(),
            OutlineNode.id.asc()
        ).limit(validated_limit + 1).all()
        
        # 检查子节点存在性
        node_ids = [n.id for n in nodes[:validated_limit]]
        children_counts = {}
        if node_ids:
            from sqlalchemy import func as sql_func
            child_counts = db.query(
                OutlineNode.parent_id,
                sql_func.count(OutlineNode.id).label('count')
            ).filter(
                OutlineNode.parent_id.in_(node_ids)
            ).group_by(OutlineNode.parent_id).all()
            children_counts = {parent_id: count for parent_id, count in child_counts}
        
        # 构建响应
        def truncate_evidence(text: Optional[str], max_len: int = 200) -> Optional[str]:
            if not text:
                return None
            return text[:max_len] + ('...' if len(text) > max_len else '')
        
        node_items = []
        for node in nodes[:validated_limit]:
            # 从meta_data中获取证据预览
            meta = node.meta_data or {}
            evidence_data = meta.get('evidence', [])
            evidence_preview = None
            evidence_full_available = False
            
            if evidence_data and len(evidence_data) > 0:
                first_evidence = evidence_data[0]
                if isinstance(first_evidence, dict):
                    evidence_text = first_evidence.get('text', '')
                    evidence_preview = truncate_evidence(evidence_text)
                    evidence_full_available = len(evidence_text) > 200 if evidence_text else False
            
            node_items.append(OutlineNodeListItem(
                id=str(node.id),
                outline_id=str(node.outline_id),
                parent_id=str(node.parent_id) if node.parent_id else None,
                node_type=node.node_type,
                title=node.title,
                summary=node.summary,
                significance=node.significance,
                sort_index=node.sort_index,
                depth=node.depth,
                path=node.path,
                chapter_start_id=str(node.chapter_start_id) if node.chapter_start_id else None,
                chapter_end_id=str(node.chapter_end_id) if node.chapter_end_id else None,
                has_children=children_counts.get(node.id, 0) > 0,
                evidence_preview=evidence_preview,
                evidence_full_available=evidence_full_available,
                events_count=len(node.events) if hasattr(node, 'events') else 0,
            ))
        
        # 创建下一页游标
        next_cursor = None
        has_more = len(nodes) > validated_limit
        
        if has_more and node_items:
            last_node = nodes[validated_limit - 1]
            cursor_obj = PaginationCursor(
                sort_index=last_node.sort_index,
                node_id=last_node.id
            )
            next_cursor = cursor_obj.encode()
        
        return PaginatedOutlineNodesResponse(
            nodes=node_items,
            next_cursor=next_cursor,
            has_more=has_more,
            total_count=total_count,
        )

    @get("/node/{node_id:str}/evidence")
    async def get_node_evidence(
        self,
        node_id: str,
        router_dependency: Generator[Session, None, None] = None,
    ) -> NodeEvidenceResponse:
        """获取节点完整证据列表"""
        db = next(router_dependency)
        
        node = db.query(OutlineNode).filter(OutlineNode.id == int(node_id)).first()
        
        if not node:
            raise NotFoundException(detail=f"Node {node_id} not found")
        
        # 从meta_data获取证据
        meta = node.meta_data or {}
        evidence_list = meta.get('evidence', [])
        
        # 格式化证据
        formatted_evidence = []
        for evidence in evidence_list:
            if isinstance(evidence, dict):
                formatted_evidence.append({
                    'text': evidence.get('text', ''),
                    'chapter_title': evidence.get('chapter_title'),
                    'start_fragment': evidence.get('start_fragment'),
                    'end_fragment': evidence.get('end_fragment'),
                })
        
        return NodeEvidenceResponse(
            node_id=str(node.id),
            evidence_list=formatted_evidence,
            total_count=len(formatted_evidence),
        )

    @get("/node/{node_id:str}/detail")
    async def get_node_detail(
        self,
        node_id: str,
        router_dependency: Generator[Session, None, None] = None,
    ) -> NodeDetailResponse:
        """获取节点完整详情"""
        db = next(router_dependency)
        
        node = db.query(OutlineNode).filter(OutlineNode.id == int(node_id)).first()
        
        if not node:
            raise NotFoundException(detail=f"Node {node_id} not found")
        
        # 获取子节点数量
        from sqlalchemy import func as sql_func
        child_count = db.query(sql_func.count(OutlineNode.id)).filter(
            OutlineNode.parent_id == node.id
        ).scalar() or 0
        
        # 获取事件
        events = []
        for event in node.events:
            events.append({
                'id': str(event.id),
                'event_type': event.event_type,
                'title': event.title,
                'description': event.description,
                'importance': event.importance,
            })
        
        return NodeDetailResponse(
            id=str(node.id),
            outline_id=str(node.outline_id),
            parent_id=str(node.parent_id) if node.parent_id else None,
            node_type=node.node_type,
            title=node.title,
            summary=node.summary,
            significance=node.significance,
            sort_index=node.sort_index,
            depth=node.depth,
            path=node.path,
            chapter_start_id=str(node.chapter_start_id) if node.chapter_start_id else None,
            chapter_end_id=str(node.chapter_end_id) if node.chapter_end_id else None,
            meta_data=node.meta_data or {},
            events=events,
            child_count=child_count,
        )

    @post("/nodes/batch-details")
    async def get_nodes_batch_details(
        self,
        data: List[str],
        router_dependency: Generator[Session, None, None] = None,
    ) -> List[NodeDetailResponse]:
        """批量获取节点详情
        
        Args:
            data: 节点ID列表 (最多50个)
        """
        db = next(router_dependency)
        
        if len(data) > 50:
            raise ClientException(detail="Maximum 50 nodes allowed per batch request")
        
        node_ids = [int(nid) for nid in data]
        
        from sqlalchemy import func as sql_func
        
        # 批量查询节点
        nodes = db.query(OutlineNode).filter(
            OutlineNode.id.in_(node_ids)
        ).all()
        
        # 批量查询子节点数量
        child_counts = db.query(
            OutlineNode.parent_id,
            sql_func.count(OutlineNode.id).label('count')
        ).filter(
            OutlineNode.parent_id.in_(node_ids)
        ).group_by(OutlineNode.parent_id).all()
        child_count_map = {parent_id: count for parent_id, count in child_counts}
        
        # 构建响应
        results = []
        for node in nodes:
            events = [
                {
                    'id': str(event.id),
                    'event_type': event.event_type,
                    'title': event.title,
                    'description': event.description,
                    'importance': event.importance,
                }
                for event in node.events
            ]
            
            results.append(NodeDetailResponse(
                id=str(node.id),
                outline_id=str(node.outline_id),
                parent_id=str(node.parent_id) if node.parent_id else None,
                node_type=node.node_type,
                title=node.title,
                summary=node.summary,
                significance=node.significance,
                sort_index=node.sort_index,
                depth=node.depth,
                path=node.path,
                chapter_start_id=str(node.chapter_start_id) if node.chapter_start_id else None,
                chapter_end_id=str(node.chapter_end_id) if node.chapter_end_id else None,
                meta_data=node.meta_data or {},
                events=events,
                child_count=child_count_map.get(node.id, 0),
            ))
        
        return results


# ============================================================================
# Export
# ============================================================================

__all__ = [
    "OutlineController",
]
