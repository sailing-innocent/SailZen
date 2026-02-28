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
from dataclasses import dataclass

from sail_server.data.analysis import (
    Outline,
    OutlineNode,
    OutlineEvent,
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
    outline_id: str
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
        """获取大纲树结构"""
        db = next(router_dependency)
        
        outline = db.query(Outline).filter(Outline.id == int(outline_id)).first()
        
        if not outline:
            raise NotFoundException(detail=f"Outline {outline_id} not found")
        
        nodes = db.query(OutlineNode).filter(
            OutlineNode.outline_id == int(outline_id)
        ).order_by(OutlineNode.sort_index).all()
        
        node_responses = [
            OutlineNodeResponse(
                id=str(node.id),
                outline_id=str(node.outline_id),
                parent_id=str(node.parent_id) if node.parent_id else None,
                node_type=node.node_type,
                title=node.title,
                summary=node.summary,
                sort_index=node.sort_index,
                created_at=node.created_at.isoformat() if node.created_at else None,
            )
            for node in nodes
        ]
        
        return OutlineTreeResponse(
            outline_id=outline_id,
            nodes=node_responses,
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


# ============================================================================
# Export
# ============================================================================

__all__ = [
    "OutlineController",
]
