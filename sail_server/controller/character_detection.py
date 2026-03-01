# -*- coding: utf-8 -*-
# @file character_detection.py
# @brief Character Detection Controller
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

from sail_server.application.dto.analysis import TextRangeSelection
from sail_server.service.character_detector import (
    CharacterDetector,
    CharacterDetectionResult as ServiceDetectionResult,
    CharacterDetectionConfig,
    DetectedCharacter,
)
from sail_server.service.character_profiler import (
    CharacterProfiler,
    ProfileBuildResult,
)
from sail_server.db import g_db_func

logger = logging.getLogger(__name__)


# ============================================================================
# Local Pydantic Models for API
# ============================================================================

class DetectedCharacterAlias(BaseModel):
    """检测到的角色别名"""
    alias: str = Field(description="别名")
    alias_type: str = Field(default="other", description="别名类型")


class DetectedCharacterAttribute(BaseModel):
    """检测到的角色属性"""
    category: str = Field(default="other", description="类别")
    key: str = Field(description="键")
    value: str = Field(description="值")
    confidence: Optional[float] = Field(default=None, description="置信度")
    source_text: Optional[str] = Field(default=None, description="来源文本")


class DetectedCharacterRelation(BaseModel):
    """检测到的角色关系"""
    target_name: str = Field(description="目标名称")
    relation_type: str = Field(default="other", description="关系类型")
    description: Optional[str] = Field(default=None, description="描述")
    evidence: Optional[str] = Field(default=None, description="证据")


class DetectedCharacterItem(BaseModel):
    """检测到的角色（API响应用）"""
    canonical_name: str = Field(description="规范名称")
    aliases: List[DetectedCharacterAlias] = Field(default_factory=list, description="别名")
    role_type: str = Field(default="supporting", description="角色类型")
    role_confidence: float = Field(default=0.5, description="角色置信度")
    first_appearance: Optional[Dict[str, str]] = Field(default=None, description="首次出现")
    description: str = Field(default="", description="描述")
    attributes: List[DetectedCharacterAttribute] = Field(default_factory=list, description="属性")
    relations: List[DetectedCharacterRelation] = Field(default_factory=list, description="关系")
    key_actions: List[str] = Field(default_factory=list, description="关键行动")
    mention_count: int = Field(default=0, description="提及次数")


class CharacterDetectionResult(BaseModel):
    """人物检测结果"""
    characters: List[DetectedCharacterItem] = Field(default_factory=list, description="角色列表")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")
    raw_response: Optional[str] = Field(default=None, description="原始响应")


class CharacterDetectionResponse(BaseModel):
    """人物检测响应"""
    success: bool = Field(description="是否成功")
    task_id: Optional[str] = Field(default=None, description="任务ID")
    result: Optional[CharacterDetectionResult] = Field(default=None, description="结果")
    message: str = Field(default="", description="消息")
    error: Optional[str] = Field(default=None, description="错误")


class CharacterMergeCandidate(BaseModel):
    """人物合并候选"""
    character1_id: int = Field(description="角色1 ID")
    character2_id: int = Field(description="角色2 ID")
    character1_name: str = Field(description="角色1名称")
    character2_name: str = Field(description="角色2名称")
    similarity_score: float = Field(description="相似度分数")
    merge_reason: str = Field(description="合并原因")
    suggested_action: str = Field(description="建议操作")


class CharacterDeduplicationResult(BaseModel):
    """人物去重结果"""
    merge_candidates: List[CharacterMergeCandidate] = Field(default_factory=list, description="合并候选")
    statistics: Dict[str, Any] = Field(default_factory=dict, description="统计信息")


# ============================================================================
# Dependency Injection
# ============================================================================

async def provide_db() -> Session:
    """提供数据库会话"""
    return next(g_db_func())


# ============================================================================
# Character Detection Controller
# ============================================================================

class CharacterDetectionController(Controller):
    """人物检测控制器
    
    提供人物检测、档案构建、去重合并等功能
    """
    
    path = "/character-detection"
    dependencies = {"db": Provide(provide_db)}
    
    @post("/")
    async def create_detection_task(
        self,
        db: Session,
        data: Dict[str, Any],
    ) -> CharacterDetectionResponse:
        """创建人物检测任务
        
        Args:
            data: 检测请求数据
                - edition_id: 版本ID
                - range_selection: 文本范围选择
                - config: 检测配置（可选）
                - work_title: 作品标题（可选）
                - known_characters: 已知人物列表（可选）
                
        Returns:
            检测响应
        """
        try:
            # 解析请求
            edition_id = data.get("edition_id")
            range_selection_data = data.get("range_selection", {})
            config_data = data.get("config", {})
            work_title = data.get("work_title", "")
            known_characters = data.get("known_characters", [])
            
            if not edition_id:
                return CharacterDetectionResponse(
                    success=False,
                    message="缺少必要参数: edition_id",
                    error="Missing edition_id",
                )
            
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
            config = CharacterDetectionConfig(
                detect_aliases=config_data.get("detect_aliases", True),
                detect_attributes=config_data.get("detect_attributes", True),
                detect_relations=config_data.get("detect_relations", True),
                min_confidence=config_data.get("min_confidence", 0.5),
                max_characters=config_data.get("max_characters", 100),
                llm_provider=config_data.get("llm_provider"),
                llm_model=config_data.get("llm_model"),
                temperature=config_data.get("temperature", 0.3),
                prompt_template_id=config_data.get("prompt_template_id", "character_detection_v2"),
            )
            
            # 生成任务ID
            import uuid
            task_id = f"char_detect_{uuid.uuid4().hex[:8]}"
            
            logger.info(f"[CharacterDetection] Starting detection task {task_id} for edition {edition_id}")
            
            # 执行检测
            detector = CharacterDetector(db)
            result = await detector.detect(
                edition_id=edition_id,
                range_selection=range_selection,
                config=config,
                work_title=work_title,
                known_characters=known_characters,
                task_id=task_id,
            )
            
            # 转换结果
            response_result = self._convert_to_response_result(result)
            
            return CharacterDetectionResponse(
                success=True,
                task_id=task_id,
                result=response_result,
                message=f"成功检测到 {len(result.characters)} 个人物",
            )
            
        except Exception as e:
            logger.error(f"[CharacterDetection] Detection failed: {e}", exc_info=True)
            return CharacterDetectionResponse(
                success=False,
                message="人物检测失败",
                error=str(e),
            )
    
    @post("/preview")
    async def preview_detection(
        self,
        db: Session,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """预览人物检测（快速预览前N章）
        
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
            config = CharacterDetectionConfig(
                detect_aliases=True,
                detect_attributes=True,
                detect_relations=False,  # 预览不检测关系
                max_characters=20,
            )
            
            # 执行检测
            detector = CharacterDetector(db)
            result = await detector.detect(
                edition_id=edition_id,
                range_selection=range_selection,
                config=config,
                work_title=work_title,
            )
            
            # 简化结果
            preview_characters = [
                {
                    "canonical_name": char.canonical_name,
                    "role_type": char.role_type,
                    "role_confidence": char.role_confidence,
                    "mention_count": char.mention_count,
                    "description": char.description[:100] + "..." if len(char.description) > 100 else char.description,
                }
                for char in result.characters[:10]  # 只返回前10个
            ]
            
            return {
                "success": True,
                "preview_characters": preview_characters,
                "total_detected": len(result.characters),
                "metadata": result.metadata,
            }
            
        except Exception as e:
            logger.error(f"[CharacterDetection] Preview failed: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    @post("/task/{task_id:str}/save")
    async def save_detection_result(
        self,
        db: Session,
        task_id: str,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """保存检测结果到数据库
        
        Args:
            task_id: 任务ID
            data: 保存请求数据
                - characters: 要保存的人物列表
                - auto_deduplicate: 是否自动去重（默认True）
                
        Returns:
            保存结果统计
        """
        try:
            characters_data = data.get("characters", [])
            auto_deduplicate = data.get("auto_deduplicate", True)
            
            if not characters_data:
                return {"success": False, "error": "没有要保存的人物数据"}
            
            profiler = CharacterProfiler(db)
            
            saved_characters = []
            for char_data in characters_data:
                result = profiler.build_profile_from_detection(
                    edition_id=char_data.get("edition_id", 0),
                    detected_character=char_data,
                    source="llm_detection",
                )
                saved_characters.append({
                    "character_id": result.character_id,
                    "canonical_name": result.profile.character.canonical_name,
                    "aliases_created": result.created_aliases,
                    "attributes_created": result.created_attributes,
                })
            
            # 自动去重
            dedup_result = None
            if auto_deduplicate and saved_characters:
                edition_id = characters_data[0].get("edition_id", 0)
                dedup_result = profiler.auto_merge_duplicates(edition_id)
            
            return {
                "success": True,
                "saved_count": len(saved_characters),
                "saved_characters": saved_characters,
                "deduplication": dedup_result,
            }
            
        except Exception as e:
            logger.error(f"[CharacterDetection] Save failed: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    @get("/deduplicate/{edition_id:int}")
    async def get_deduplication_candidates(
        self,
        db: Session,
        edition_id: int,
        min_similarity: float = 0.7,
    ) -> Dict[str, Any]:
        """获取人物去重候选
        
        Args:
            edition_id: 版本ID
            min_similarity: 最小相似度阈值（默认0.7）
            
        Returns:
            去重候选列表
        """
        try:
            profiler = CharacterProfiler(db)
            result = profiler.find_duplicate_candidates(edition_id, min_similarity)
            
            candidates = [
                {
                    "character1_id": c.character1_id,
                    "character2_id": c.character2_id,
                    "character1_name": c.character1_name,
                    "character2_name": c.character2_name,
                    "similarity_score": c.similarity_score,
                    "merge_reason": c.merge_reason,
                    "suggested_action": c.suggested_action,
                }
                for c in result.merge_candidates
            ]
            
            return {
                "success": True,
                "candidates": candidates,
                "statistics": result.statistics,
            }
            
        except Exception as e:
            logger.error(f"[CharacterDetection] Deduplication check failed: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    @post("/merge")
    async def merge_characters(
        self,
        db: Session,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """合并两个人物
        
        Args:
            data: 合并请求数据
                - target_character_id: 保留的目标人物ID
                - source_character_id: 被合并的源人物ID
                
        Returns:
            合并结果
        """
        try:
            target_id = data.get("target_character_id")
            source_id = data.get("source_character_id")
            
            if not target_id or not source_id:
                return {"success": False, "error": "缺少 target_character_id 或 source_character_id"}
            
            profiler = CharacterProfiler(db)
            merged = profiler.merge_characters(target_id, source_id)
            
            if merged:
                return {
                    "success": True,
                    "merged_character_id": merged.id,
                    "merged_character_name": merged.canonical_name,
                }
            else:
                return {"success": False, "error": "合并失败，人物不存在"}
                
        except Exception as e:
            logger.error(f"[CharacterDetection] Merge failed: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    @post("/batch-import")
    async def batch_import_characters(
        self,
        db: Session,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """批量导入人物
        
        Args:
            data: 批量导入请求数据
                - edition_id: 版本ID
                - characters: 人物数据列表
                - auto_deduplicate: 是否自动去重（默认True）
                
        Returns:
            导入结果
        """
        try:
            edition_id = data.get("edition_id")
            characters_data = data.get("characters", [])
            auto_deduplicate = data.get("auto_deduplicate", True)
            
            if not edition_id:
                return {"success": False, "error": "缺少 edition_id"}
            
            if not characters_data:
                return {"success": False, "error": "没有要导入的人物数据"}
            
            profiler = CharacterProfiler(db)
            
            imported = []
            errors = []
            
            for i, char_data in enumerate(characters_data):
                try:
                    result = profiler.build_profile_from_detection(
                        edition_id=edition_id,
                        detected_character=char_data,
                        source="batch_import",
                    )
                    imported.append({
                        "index": i,
                        "character_id": result.character_id,
                        "canonical_name": result.profile.character.canonical_name,
                        "aliases_created": result.created_aliases,
                        "attributes_created": result.created_attributes,
                    })
                except Exception as e:
                    errors.append({"index": i, "error": str(e)})
            
            # 自动去重
            dedup_result = None
            if auto_deduplicate:
                dedup_result = profiler.auto_merge_duplicates(edition_id)
            
            return {
                "success": True,
                "imported_count": len(imported),
                "error_count": len(errors),
                "imported": imported,
                "errors": errors,
                "deduplication": dedup_result,
            }
            
        except Exception as e:
            logger.error(f"[CharacterDetection] Batch import failed: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    def _convert_to_response_result(
        self,
        service_result: ServiceDetectionResult,
    ) -> CharacterDetectionResult:
        """转换服务层结果到响应格式"""
        characters = []
        for char in service_result.characters:
            # 转换别名
            aliases = [
                DetectedCharacterAlias(
                    alias=a.get("alias", ""),
                    alias_type=a.get("alias_type", "other"),
                )
                for a in char.aliases
            ]
            
            # 转换属性
            attributes = [
                DetectedCharacterAttribute(
                    category=a.get("category", "other"),
                    key=a.get("key", ""),
                    value=a.get("value", ""),
                    confidence=a.get("confidence"),
                    source_text=a.get("source_text"),
                )
                for a in char.attributes
            ]
            
            # 转换关系
            relations = [
                DetectedCharacterRelation(
                    target_name=r.get("target_name", ""),
                    relation_type=r.get("relation_type", "other"),
                    description=r.get("description"),
                    evidence=r.get("evidence"),
                )
                for r in char.relations
            ]
            
            characters.append(DetectedCharacterItem(
                canonical_name=char.canonical_name,
                aliases=aliases,
                role_type=char.role_type,
                role_confidence=char.role_confidence,
                first_appearance=char.first_appearance,
                description=char.description,
                attributes=attributes,
                relations=relations,
                key_actions=char.key_actions,
                mention_count=char.mention_count,
            ))
        
        return CharacterDetectionResult(
            characters=characters,
            metadata=service_result.metadata,
            raw_response=service_result.raw_response,
        )
