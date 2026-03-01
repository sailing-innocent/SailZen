# -*- coding: utf-8 -*-
# @file setting_extraction.py
# @brief Setting Extraction Controller
# @author sailing-innocent
# @date 2025-03-01
# @version 1.0
# ---------------------------------

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

from litestar import Controller, post, get
from litestar.di import Provide
from litestar.exceptions import HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from sail_server.data.analysis import TextRangeSelection
from sail_server.service.setting_extractor import (
    SettingExtractor,
    SettingExtractionResult as ServiceExtractionResult,
    ExtractedSetting,
    SettingExtractionConfig,
)
from sail_server.model.analysis.setting import (
    Setting,
    SettingAttribute,
    SettingRelation,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Local Pydantic Models for API
# ============================================================================

class SettingAttributeData(BaseModel):
    """设定属性数据"""
    key: str = Field(description="键")
    value: str = Field(description="值")


class SettingRelationData(BaseModel):
    """设定关系数据"""
    target_name: str = Field(description="目标名称")
    relation_type: str = Field(description="关系类型")
    description: Optional[str] = Field(default=None, description="描述")


class ExtractedSettingItem(BaseModel):
    """提取的设定项（API用）"""
    canonical_name: str = Field(description="规范名称")
    setting_type: str = Field(description="设定类型")
    category: Optional[str] = Field(default=None, description="分类")
    importance: str = Field(default="minor", description="重要性")
    first_appearance: Optional[Dict[str, str]] = Field(default=None, description="首次出现")
    description: str = Field(default="", description="描述")
    attributes: List[Dict[str, str]] = Field(default_factory=list, description="属性")
    relations: List[Dict[str, str]] = Field(default_factory=list, description="关系")
    key_scenes: List[str] = Field(default_factory=list, description="关键场景")
    mention_count: int = Field(default=0, description="提及次数")


class SettingExtractionResult(BaseModel):
    """设定提取结果"""
    settings: List[ExtractedSettingItem] = Field(default_factory=list, description="设定列表")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")


# ============================================================================
# Setting Extraction Controller
# ============================================================================

class SettingExtractionController(Controller):
    """设定提取控制器
    
    提供设定提取、关系管理等功能
    """
    
    path = "/setting-extraction"
    
    @post("/")
    async def create_extraction_task(
        self,
        db: Session,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """创建设定提取任务
        
        Args:
            data: 提取请求数据
                - edition_id: 版本ID
                - range_selection: 文本范围选择
                - config: 提取配置（可选）
                - work_title: 作品标题（可选）
                - known_settings: 已知设定列表（可选）
                
        Returns:
            提取响应
        """
        try:
            # 解析请求
            edition_id = data.get("edition_id")
            range_selection_data = data.get("range_selection", {})
            config_data = data.get("config", {})
            work_title = data.get("work_title", "")
            known_settings = data.get("known_settings", [])
            
            if not edition_id:
                return {
                    "success": False,
                    "message": "缺少必要参数: edition_id",
                    "error": "Missing edition_id",
                }
            
            # 构建范围选择
            range_selection = TextRangeSelection(
                edition_id=edition_id,
                mode=range_selection_data.get("mode", "full_edition"),
                chapter_index=range_selection_data.get("chapter_index"),
                start_index=range_selection_data.get("start_index"),
                end_index=range_selection_data.get("end_index"),
                chapter_indices=range_selection_data.get("chapter_indices", []),
                node_ids=range_selection_data.get("node_ids", []),
            )
            
            # 构建配置
            config = SettingExtractionConfig(
                setting_types=config_data.get("setting_types", [
                    "item", "location", "organization", "concept", 
                    "magic_system", "creature", "event_type"
                ]),
                min_importance=config_data.get("min_importance", "background"),
                extract_relations=config_data.get("extract_relations", True),
                extract_attributes=config_data.get("extract_attributes", True),
                max_settings=config_data.get("max_settings", 100),
                llm_provider=config_data.get("llm_provider"),
                llm_model=config_data.get("llm_model"),
                temperature=config_data.get("temperature", 0.3),
                prompt_template_id=config_data.get("prompt_template_id", "setting_extraction_v1"),
            )
            
            # 生成任务ID
            import uuid
            task_id = f"setting_extract_{uuid.uuid4().hex[:8]}"
            
            logger.info(f"[SettingExtraction] Starting extraction task {task_id} for edition {edition_id}")
            
            # 执行提取
            extractor = SettingExtractor(db)
            result = await extractor.extract(
                edition_id=edition_id,
                range_selection=range_selection,
                config=config,
                work_title=work_title,
                known_settings=known_settings,
                task_id=task_id,
            )
            
            # 转换结果
            response_result = self._convert_to_response_result(result)
            
            return {
                "success": True,
                "task_id": task_id,
                "result": response_result.model_dump(),
                "message": f"成功提取 {len(result.settings)} 个设定",
            }
            
        except Exception as e:
            logger.error(f"[SettingExtraction] Extraction failed: {e}", exc_info=True)
            return {
                "success": False,
                "message": "设定提取失败",
                "error": str(e),
            }
    
    @post("/preview")
    async def preview_extraction(
        self,
        db: Session,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """预览设定提取（快速预览前N章）
        
        Args:
            data: 预览请求数据
                - edition_id: 版本ID
                - chapter_count: 预览章节数（默认3章）
                - work_title: 作品标题（可选）
                
        Returns:
            预览结果
        """
        try:
            edition_id = data.get("edition_id")
            chapter_count = data.get("chapter_count", 3)
            work_title = data.get("work_title", "")
            
            if not edition_id:
                return {"success": False, "error": "缺少 edition_id"}
            
            # 构建范围选择（前N章）
            range_selection = TextRangeSelection(
                edition_id=edition_id,
                mode="chapter_range",
                start_index=0,
                end_index=chapter_count - 1,
            )
            
            # 使用简化配置
            config = SettingExtractionConfig(
                extract_relations=False,  # 预览不提取关系
                max_settings=20,
            )
            
            # 执行提取
            extractor = SettingExtractor(db)
            result = await extractor.extract(
                edition_id=edition_id,
                range_selection=range_selection,
                config=config,
                work_title=work_title,
            )
            
            # 简化结果
            preview_settings = [
                {
                    "canonical_name": setting.canonical_name,
                    "setting_type": setting.setting_type,
                    "category": setting.category,
                    "importance": setting.importance,
                    "mention_count": setting.mention_count,
                    "description": setting.description[:100] + "..." if len(setting.description) > 100 else setting.description,
                }
                for setting in result.settings[:10]  # 只返回前10个
            ]
            
            return {
                "success": True,
                "preview_settings": preview_settings,
                "total_detected": len(result.settings),
                "metadata": result.metadata,
            }
            
        except Exception as e:
            logger.error(f"[SettingExtraction] Preview failed: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    @post("/task/{task_id:str}/save")
    async def save_extraction_result(
        self,
        db: Session,
        task_id: str,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """保存提取结果到数据库
        
        Args:
            task_id: 任务ID
            data: 保存请求数据
                - settings: 要保存的设定列表
                - edition_id: 版本ID
                
        Returns:
            保存结果统计
        """
        try:
            settings_data = data.get("settings", [])
            edition_id = data.get("edition_id")
            
            if not edition_id:
                return {"success": False, "error": "缺少 edition_id"}
            
            if not settings_data:
                return {"success": False, "error": "没有要保存的设定数据"}
            
            saved_settings = []
            
            for setting_data in settings_data:
                # 创建或更新设定
                setting = self._create_or_update_setting(
                    db=db,
                    edition_id=edition_id,
                    name=setting_data.get("canonical_name", ""),
                    setting_type=setting_data.get("setting_type", "item"),
                    category=setting_data.get("category"),
                    description=setting_data.get("description", ""),
                    importance=setting_data.get("importance", "minor"),
                )
                
                # 添加属性
                attributes_count = 0
                for attr_data in setting_data.get("attributes", []):
                    self._add_attribute(
                        db=db,
                        setting_id=setting.id,
                        key=attr_data.get("key", ""),
                        value=attr_data.get("value", ""),
                    )
                    attributes_count += 1
                
                saved_settings.append({
                    "setting_id": setting.id,
                    "canonical_name": setting.canonical_name,
                    "attributes_created": attributes_count,
                })
            
            return {
                "success": True,
                "saved_count": len(saved_settings),
                "saved_settings": saved_settings,
            }
            
        except Exception as e:
            logger.error(f"[SettingExtraction] Save failed: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    @get("/relations/{edition_id:int}")
    async def get_setting_relations(
        self,
        db: Session,
        edition_id: int,
    ) -> Dict[str, Any]:
        """获取设定关系图数据
        
        Args:
            edition_id: 版本ID
            
        Returns:
            关系图数据（节点和边）
        """
        try:
            # 获取该版本的所有设定
            settings = db.query(Setting).filter(
                Setting.edition_id == edition_id
            ).all()
            
            # 构建节点
            nodes = []
            setting_id_map = {}
            for i, setting in enumerate(settings):
                node_id = f"setting_{setting.id}"
                setting_id_map[setting.id] = node_id
                nodes.append({
                    "id": node_id,
                    "name": setting.canonical_name,
                    "type": setting.setting_type,
                    "importance": setting.importance,
                    "category": setting.category,
                })
            
            # 构建边（关系）
            edges = []
            relations = db.query(SettingRelation).filter(
                SettingRelation.edition_id == edition_id
            ).all()
            
            for relation in relations:
                source_id = setting_id_map.get(relation.source_setting_id)
                target_id = setting_id_map.get(relation.target_setting_id)
                
                if source_id and target_id:
                    edges.append({
                        "id": f"rel_{relation.id}",
                        "source": source_id,
                        "target": target_id,
                        "type": relation.relation_type,
                        "description": relation.description,
                    })
            
            return {
                "success": True,
                "nodes": nodes,
                "edges": edges,
                "total_nodes": len(nodes),
                "total_edges": len(edges),
            }
            
        except Exception as e:
            logger.error(f"[SettingExtraction] Get relations failed: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    @post("/relations")
    async def create_setting_relation(
        self,
        db: Session,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """创建设定关系
        
        Args:
            data: 关系数据
                - edition_id: 版本ID
                - source_setting_id: 源设定ID
                - target_setting_id: 目标设定ID
                - relation_type: 关系类型
                - description: 关系描述（可选）
                
        Returns:
            创建结果
        """
        try:
            edition_id = data.get("edition_id")
            source_id = data.get("source_setting_id")
            target_id = data.get("target_setting_id")
            relation_type = data.get("relation_type")
            description = data.get("description")
            
            if not all([edition_id, source_id, target_id, relation_type]):
                return {"success": False, "error": "缺少必要参数"}
            
            relation = SettingRelation(
                edition_id=edition_id,
                source_setting_id=source_id,
                target_setting_id=target_id,
                relation_type=relation_type,
                description=description,
            )
            db.add(relation)
            db.commit()
            
            return {
                "success": True,
                "relation_id": relation.id,
                "message": "关系创建成功",
            }
            
        except Exception as e:
            logger.error(f"[SettingExtraction] Create relation failed: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    def _create_or_update_setting(
        self,
        db: Session,
        edition_id: int,
        name: str,
        setting_type: str,
        category: Optional[str] = None,
        description: Optional[str] = None,
        importance: str = "minor",
    ) -> Setting:
        """创建或更新设定"""
        # 检查是否已存在
        existing = db.query(Setting).filter(
            Setting.edition_id == edition_id,
            Setting.canonical_name == name,
        ).first()
        
        if existing:
            # 更新现有记录
            if description and not existing.description:
                existing.description = description
            if category and not existing.category:
                existing.category = category
            # 重要性取较高者
            importance_order = {"critical": 0, "major": 1, "minor": 2, "background": 3}
            if importance_order.get(importance, 4) < importance_order.get(existing.importance, 4):
                existing.importance = importance
            existing.updated_at = datetime.now()
            db.commit()
            return existing
        
        # 创建新记录
        setting = Setting(
            edition_id=edition_id,
            canonical_name=name,
            setting_type=setting_type,
            category=category,
            description=description,
            importance=importance,
            status="draft",
            source="extraction",
        )
        db.add(setting)
        db.commit()
        
        return setting
    
    def _add_attribute(
        self,
        db: Session,
        setting_id: int,
        key: str,
        value: str,
    ) -> Optional[SettingAttribute]:
        """添加设定属性"""
        if not key or not value:
            return None
        
        # 检查是否已存在相同键的属性
        existing = db.query(SettingAttribute).filter(
            SettingAttribute.setting_id == setting_id,
            SettingAttribute.attr_key == key,
        ).first()
        
        if existing:
            # 更新值
            existing.attr_value = value
            db.commit()
            return existing
        
        attr = SettingAttribute(
            setting_id=setting_id,
            attr_key=key,
            attr_value=value,
            source="extraction",
            status="pending",
        )
        db.add(attr)
        db.commit()
        
        return attr
    
    def _convert_to_response_result(
        self,
        service_result: ServiceExtractionResult,
    ) -> SettingExtractionResult:
        """转换服务层结果到响应格式"""
        settings = []
        for setting in service_result.settings:
            settings.append(ExtractedSettingItem(
                canonical_name=setting.canonical_name,
                setting_type=setting.setting_type,
                category=setting.category,
                importance=setting.importance,
                first_appearance=setting.first_appearance,
                description=setting.description,
                attributes=setting.attributes,
                relations=setting.relations,
                key_scenes=setting.key_scenes,
                mention_count=setting.mention_count,
            ))
        
        return SettingExtractionResult(
            settings=settings,
            metadata=service_result.metadata,
        )
