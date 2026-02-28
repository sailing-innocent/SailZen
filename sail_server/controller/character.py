# -*- coding: utf-8 -*-
# @file character.py
# @brief Character Management Controller
# @author sailing-innocent
# @date 2025-03-01
# @version 1.0
# ---------------------------------

from typing import Optional, List, Dict, Any
from litestar import Controller, get, post, delete
from litestar.di import Provide
from sqlalchemy.orm import Session

from sail_server.db import provide_db_session
from sail_server.data.analysis import CharacterData
from sail_server.model.analysis.character import (
    create_character_impl,
    get_character_impl,
    get_characters_by_edition_impl,
    update_character_impl,
    delete_character_impl,
    add_character_alias_impl,
    remove_character_alias_impl,
    add_character_attribute_impl,
    delete_character_attribute_impl,
    add_character_relation_impl,
    get_character_relations_impl,
    delete_character_relation_impl,
    get_character_profile_impl,
)
from sail_server.model.analysis.relation import get_relation_graph_impl


class CharacterController(Controller):
    """人物管理控制器"""
    path = "/character"
    dependencies = {"db": Provide(provide_db_session)}
    
    @post("/")
    async def create_character(
        self,
        data: Dict[str, Any],
        db: Session,
    ) -> Dict[str, Any]:
        """创建人物"""
        character_data = CharacterData(**data)
        result = create_character_impl(db, character_data)
        return {"success": True, "data": result}
    
    @get("/{character_id:int}")
    async def get_character(
        self,
        character_id: int,
        db: Session,
    ) -> Dict[str, Any]:
        """获取人物详情"""
        result = get_character_impl(db, character_id)
        if not result:
            return {"success": False, "error": "Character not found"}
        return {"success": True, "data": result}
    
    @get("/edition/{edition_id:int}")
    async def get_characters_by_edition(
        self,
        edition_id: int,
        db: Session,
        role_type: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """获取版本的所有人物"""
        results = get_characters_by_edition_impl(db, edition_id, role_type, status)
        return {"success": True, "data": results}
    
    @post("/{character_id:int}")
    async def update_character(
        self,
        character_id: int,
        data: Dict[str, Any],
        db: Session,
    ) -> Dict[str, Any]:
        """更新人物"""
        result = update_character_impl(db, character_id, data)
        if not result:
            return {"success": False, "error": "Character not found"}
        return {"success": True, "data": result}
    
    @delete("/{character_id:int}", status_code=200)
    async def delete_character(
        self,
        character_id: int,
        db: Session,
    ) -> Dict[str, Any]:
        """删除人物"""
        success = delete_character_impl(db, character_id)
        return {"success": success}
    
    # ========================================================================
    # Alias Operations
    # ========================================================================
    
    @post("/{character_id:int}/alias")
    async def add_alias(
        self,
        character_id: int,
        data: Dict[str, Any],
        db: Session,
    ) -> Dict[str, Any]:
        """添加人物别名"""
        result = add_character_alias_impl(
            db,
            character_id=character_id,
            alias=data.get("alias", ""),
            alias_type=data.get("alias_type", "nickname"),
            usage_context=data.get("usage_context"),
            is_preferred=data.get("is_preferred", False),
        )
        return {"success": True, "data": result}
    
    @delete("/alias/{alias_id:int}", status_code=200)
    async def remove_alias(
        self,
        alias_id: int,
        db: Session,
    ) -> Dict[str, Any]:
        """删除人物别名"""
        success = remove_character_alias_impl(db, alias_id)
        return {"success": success}
    
    # ========================================================================
    # Attribute Operations
    # ========================================================================
    
    @post("/{character_id:int}/attribute")
    async def add_attribute(
        self,
        character_id: int,
        data: Dict[str, Any],
        db: Session,
    ) -> Dict[str, Any]:
        """添加人物属性"""
        result = add_character_attribute_impl(
            db,
            character_id=character_id,
            attr_key=data.get("attr_key", ""),
            attr_value=data.get("attr_value", ""),
            category=data.get("category"),
            confidence=data.get("confidence"),
            source_node_id=data.get("source_node_id"),
        )
        return {"success": True, "data": result}
    
    @delete("/attribute/{attribute_id:int}", status_code=200)
    async def delete_attribute(
        self,
        attribute_id: int,
        db: Session,
    ) -> Dict[str, Any]:
        """删除人物属性"""
        success = delete_character_attribute_impl(db, attribute_id)
        return {"success": success}
    
    # ========================================================================
    # Relation Operations
    # ========================================================================
    
    @post("/relation")
    async def add_relation(
        self,
        data: Dict[str, Any],
        db: Session,
    ) -> Dict[str, Any]:
        """添加人物关系"""
        result = add_character_relation_impl(
            db,
            edition_id=data.get("edition_id", 0),
            source_character_id=data.get("source_character_id", 0),
            target_character_id=data.get("target_character_id", 0),
            relation_type=data.get("relation_type", ""),
            relation_subtype=data.get("relation_subtype"),
            description=data.get("description"),
            strength=data.get("strength"),
            is_mutual=data.get("is_mutual", True),
        )
        return {"success": True, "data": result}
    
    @get("/{character_id:int}/relations")
    async def get_relations(
        self,
        character_id: int,
        db: Session,
        relation_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """获取人物关系"""
        results = get_character_relations_impl(db, character_id, relation_type)
        return {"success": True, "data": results}
    
    @delete("/relation/{relation_id:int}", status_code=200)
    async def delete_relation(
        self,
        relation_id: int,
        db: Session,
    ) -> Dict[str, Any]:
        """删除人物关系"""
        success = delete_character_relation_impl(db, relation_id)
        return {"success": success}
    
    @get("/{character_id:int}/profile")
    async def get_character_profile(
        self,
        character_id: int,
        db: Session,
    ) -> Dict[str, Any]:
        """获取人物档案"""
        result = get_character_profile_impl(db, character_id)
        if not result:
            return {"success": False, "error": "Character profile not found"}
        return {"success": True, "data": result}
    
    @get("/edition/{edition_id:int}/relation-graph")
    async def get_relation_graph(
        self,
        edition_id: int,
        db: Session,
    ) -> Dict[str, Any]:
        """获取版本的关系图"""
        result = get_relation_graph_impl(db, edition_id)
        return {"success": True, "data": result}
