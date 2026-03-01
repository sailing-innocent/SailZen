# -*- coding: utf-8 -*-
# @file setting.py
# @brief Setting Management Controller
# @author sailing-innocent
# @date 2025-03-01
# @version 1.0
# ---------------------------------

from typing import Optional, List, Dict, Any
from litestar import Controller, get, post, delete
from litestar.di import Provide
from sqlalchemy.orm import Session

from sail_server.db import provide_db_session
from sail_server.application.dto.analysis import (
    SettingCreateRequest,
    SettingResponse,
)
from sail_server.model.analysis.setting import (
    create_setting_impl,
    get_setting_impl,
    get_settings_by_edition_impl,
    update_setting_impl,
    delete_setting_impl,
    add_setting_attribute_impl,
    delete_setting_attribute_impl,
    add_setting_relation_impl,
    get_setting_relations_impl,
    delete_setting_relation_impl,
    get_setting_types_impl,
)


class SettingController(Controller):
    """设定管理控制器"""
    path = "/setting"
    dependencies = {"db": Provide(provide_db_session)}
    
    @post("/")
    async def create_setting(
        self,
        data: SettingCreateRequest,
        db: Session,
    ) -> Dict[str, Any]:
        """创建设定"""
        result = create_setting_impl(db, data)
        return {"success": True, "data": SettingResponse.model_validate(result).model_dump()}
    
    @get("/{setting_id:int}")
    async def get_setting(
        self,
        setting_id: int,
        db: Session,
    ) -> Dict[str, Any]:
        """获取设定详情"""
        result = get_setting_impl(db, setting_id)
        if not result:
            return {"success": False, "error": "Setting not found"}
        return {"success": True, "data": SettingResponse.model_validate(result).model_dump()}
    
    @get("/edition/{edition_id:int}")
    async def get_settings_by_edition(
        self,
        edition_id: int,
        db: Session,
        setting_type: Optional[str] = None,
        category: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """获取版本的所有设定"""
        results = get_settings_by_edition_impl(
            db, edition_id, setting_type, category, status
        )
        return {"success": True, "data": [SettingResponse.model_validate(r).model_dump() for r in results]}
    
    @post("/{setting_id:int}")
    async def update_setting(
        self,
        setting_id: int,
        data: Dict[str, Any],
        db: Session,
    ) -> Dict[str, Any]:
        """更新设定"""
        result = update_setting_impl(db, setting_id, data)
        if not result:
            return {"success": False, "error": "Setting not found"}
        return {"success": True, "data": SettingResponse.model_validate(result).model_dump()}
    
    @delete("/{setting_id:int}", status_code=200)
    async def delete_setting(
        self,
        setting_id: int,
        db: Session,
    ) -> Dict[str, Any]:
        """删除设定"""
        success = delete_setting_impl(db, setting_id)
        return {"success": success}
    
    @get("/types")
    async def get_setting_types(
        self,
    ) -> Dict[str, Any]:
        """获取设定类型列表"""
        result = get_setting_types_impl()
        return {"success": True, **result}
    
    # ========================================================================
    # Attribute Operations
    # ========================================================================
    
    @post("/{setting_id:int}/attribute")
    async def add_attribute(
        self,
        setting_id: int,
        data: Dict[str, Any],
        db: Session,
    ) -> Dict[str, Any]:
        """添加设定属性"""
        result = add_setting_attribute_impl(
            db,
            setting_id=setting_id,
            attr_key=data.get("attr_key", ""),
            attr_value=data.get("attr_value", ""),
            source_node_id=data.get("source_node_id"),
        )
        return {"success": True, "data": result}
    
    @delete("/attribute/{attribute_id:int}", status_code=200)
    async def delete_attribute(
        self,
        attribute_id: int,
        db: Session,
    ) -> Dict[str, Any]:
        """删除设定属性"""
        success = delete_setting_attribute_impl(db, attribute_id)
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
        """添加设定关系"""
        result = add_setting_relation_impl(
            db,
            edition_id=data.get("edition_id", 0),
            source_setting_id=data.get("source_setting_id", 0),
            target_setting_id=data.get("target_setting_id", 0),
            relation_type=data.get("relation_type", ""),
            description=data.get("description"),
        )
        return {"success": True, "data": result}
    
    @get("/{setting_id:int}/relations")
    async def get_relations(
        self,
        setting_id: int,
        db: Session,
        relation_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """获取设定关系"""
        results = get_setting_relations_impl(db, setting_id, relation_type)
        return {"success": True, "data": results}
    
    @delete("/relation/{relation_id:int}", status_code=200)
    async def delete_relation(
        self,
        relation_id: int,
        db: Session,
    ) -> Dict[str, Any]:
        """删除设定关系"""
        success = delete_setting_relation_impl(db, relation_id)
        return {"success": success}
