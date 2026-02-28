# -*- coding: utf-8 -*-
# @file character_profiler.py
# @brief Character Profile Builder Service
# @author sailing-innocent
# @date 2025-03-01
# @version 1.0
# ---------------------------------

import json
import logging
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from difflib import SequenceMatcher

from sqlalchemy.orm import Session
from sqlalchemy import func

from sail_server.data.analysis import (
    CharacterData,
    CharacterAliasData,
    CharacterAttributeData,
    CharacterRelationData,
    CharacterProfile,
)
from sail_server.model.analysis.character import (
    Character,
    CharacterAlias,
    CharacterAttribute,
    CharacterRelation,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class CharacterMergeCandidate:
    """人物合并候选"""
    character1_id: int
    character2_id: int
    character1_name: str
    character2_name: str
    similarity_score: float
    merge_reason: str
    suggested_action: str  # "merge", "review", "ignore"


@dataclass
class CharacterDeduplicationResult:
    """人物去重结果"""
    merged_groups: List[List[int]]  # 合并的字符ID组
    merge_candidates: List[CharacterMergeCandidate]
    statistics: Dict[str, Any]


@dataclass
class ProfileBuildResult:
    """档案构建结果"""
    character_id: int
    profile: CharacterProfile
    created_aliases: int
    created_attributes: int
    created_relations: int


# ============================================================================
# Character Profiler Service
# ============================================================================

class CharacterProfiler:
    """人物画像构建服务
    
    负责：
    - 从检测结果构建完整的人物档案
    - 人物去重和合并
    - 属性整合
    - 关系映射
    """
    
    # 相似度阈值
    NAME_SIMILARITY_THRESHOLD = 0.8
    ALIAS_MATCH_THRESHOLD = 0.9
    
    def __init__(self, db: Session):
        self.db = db
    
    def build_profile_from_detection(
        self,
        edition_id: int,
        detected_character: Dict[str, Any],
        source: str = "llm_detection",
    ) -> ProfileBuildResult:
        """从检测结果构建人物档案
        
        Args:
            edition_id: 版本ID
            detected_character: 检测到的人物数据
            source: 数据来源
            
        Returns:
            档案构建结果
        """
        # 1. 创建或更新人物主体
        character = self._create_or_update_character(
            edition_id=edition_id,
            canonical_name=detected_character.get("canonical_name", ""),
            role_type=detected_character.get("role_type", "supporting"),
            description=detected_character.get("description", ""),
            source=source,
        )
        
        created_aliases = 0
        created_attributes = 0
        created_relations = 0
        
        # 2. 添加别名
        aliases = detected_character.get("aliases", [])
        for alias_data in aliases:
            alias = self._add_alias(
                character_id=character.id,
                alias=alias_data.get("alias", ""),
                alias_type=alias_data.get("alias_type", "other"),
                source=source,
            )
            if alias:
                created_aliases += 1
        
        # 3. 添加属性
        attributes = detected_character.get("attributes", [])
        for attr_data in attributes:
            attr = self._add_attribute(
                character_id=character.id,
                category=attr_data.get("category", "other"),
                key=attr_data.get("key", ""),
                value=attr_data.get("value", ""),
                confidence=attr_data.get("confidence"),
                source=source,
            )
            if attr:
                created_attributes += 1
        
        # 4. 添加关系（需要在所有人物创建后处理）
        # 关系将在批量导入时处理
        
        # 5. 构建档案
        profile = self._build_character_profile(character.id)
        
        return ProfileBuildResult(
            character_id=character.id,
            profile=profile,
            created_aliases=created_aliases,
            created_attributes=created_attributes,
            created_relations=created_relations,
        )
    
    def find_duplicate_candidates(
        self,
        edition_id: int,
        min_similarity: float = 0.7,
    ) -> CharacterDeduplicationResult:
        """查找可能重复的人物候选
        
        Args:
            edition_id: 版本ID
            min_similarity: 最小相似度阈值
            
        Returns:
            去重候选结果
        """
        # 获取该版本的所有人物
        characters = self.db.query(Character).filter(
            Character.edition_id == edition_id
        ).all()
        
        candidates = []
        
        # 两两比较
        for i, char1 in enumerate(characters):
            for char2 in characters[i + 1:]:
                similarity, reason = self._calculate_character_similarity(char1, char2)
                
                if similarity >= min_similarity:
                    # 确定建议操作
                    if similarity >= self.NAME_SIMILARITY_THRESHOLD:
                        action = "merge"
                    elif similarity >= 0.75:
                        action = "review"
                    else:
                        action = "ignore"
                    
                    candidate = CharacterMergeCandidate(
                        character1_id=char1.id,
                        character2_id=char2.id,
                        character1_name=char1.canonical_name,
                        character2_name=char2.canonical_name,
                        similarity_score=similarity,
                        merge_reason=reason,
                        suggested_action=action,
                    )
                    candidates.append(candidate)
        
        # 按相似度排序
        candidates.sort(key=lambda c: c.similarity_score, reverse=True)
        
        # 统计
        statistics = {
            "total_characters": len(characters),
            "high_confidence_duplicates": sum(1 for c in candidates if c.suggested_action == "merge"),
            "medium_confidence_duplicates": sum(1 for c in candidates if c.suggested_action == "review"),
            "total_candidates": len(candidates),
        }
        
        return CharacterDeduplicationResult(
            merged_groups=[],  # 实际合并操作需要人工确认
            merge_candidates=candidates,
            statistics=statistics,
        )
    
    def merge_characters(
        self,
        target_character_id: int,
        source_character_id: int,
        merge_strategy: str = "smart",
    ) -> Optional[Character]:
        """合并两个人物
        
        Args:
            target_character_id: 保留的目标人物ID
            source_character_id: 被合并的源人物ID
            merge_strategy: 合并策略 (smart, keep_target, keep_source)
            
        Returns:
            合并后的人物
        """
        target = self.db.query(Character).get(target_character_id)
        source = self.db.query(Character).get(source_character_id)
        
        if not target or not source:
            logger.error(f"[Profiler] Cannot merge: character not found")
            return None
        
        # 1. 合并别名
        self._merge_aliases(target, source)
        
        # 2. 合并属性
        self._merge_attributes(target, source, merge_strategy)
        
        # 3. 迁移关系
        self._migrate_relations(target, source)
        
        # 4. 更新描述（如果目标没有描述）
        if not target.description and source.description:
            target.description = source.description
        
        # 5. 删除源人物
        self.db.delete(source)
        self.db.commit()
        
        logger.info(f"[Profiler] Merged character {source.canonical_name} into {target.canonical_name}")
        
        return target
    
    def auto_merge_duplicates(
        self,
        edition_id: int,
        similarity_threshold: float = 0.85,
    ) -> Dict[str, Any]:
        """自动合并高置信度的重复人物
        
        Args:
            edition_id: 版本ID
            similarity_threshold: 相似度阈值
            
        Returns:
            合并结果统计
        """
        result = self.find_duplicate_candidates(edition_id, min_similarity=similarity_threshold)
        
        merged_count = 0
        merged_groups = []
        
        for candidate in result.merge_candidates:
            if candidate.suggested_action == "merge":
                # 保留更完整的人物作为目标
                char1 = self.db.query(Character).get(candidate.character1_id)
                char2 = self.db.query(Character).get(candidate.character2_id)
                
                # 简单的启发式：保留有更多属性的人物
                attr_count1 = self.db.query(CharacterAttribute).filter(
                    CharacterAttribute.character_id == char1.id
                ).count()
                attr_count2 = self.db.query(CharacterAttribute).filter(
                    CharacterAttribute.character_id == char2.id
                ).count()
                
                if attr_count1 >= attr_count2:
                    target_id, source_id = char1.id, char2.id
                else:
                    target_id, source_id = char2.id, char1.id
                
                merged = self.merge_characters(target_id, source_id)
                if merged:
                    merged_count += 1
                    merged_groups.append([candidate.character1_id, candidate.character2_id])
        
        return {
            "merged_count": merged_count,
            "merged_groups": merged_groups,
            "remaining_candidates": len(result.merge_candidates) - merged_count,
        }
    
    def _create_or_update_character(
        self,
        edition_id: int,
        canonical_name: str,
        role_type: str = "supporting",
        description: Optional[str] = None,
        source: str = "manual",
    ) -> Character:
        """创建或更新人物"""
        # 检查是否已存在
        existing = self.db.query(Character).filter(
            Character.edition_id == edition_id,
            Character.canonical_name == canonical_name,
        ).first()
        
        if existing:
            # 更新现有记录
            if description and not existing.description:
                existing.description = description
            if role_type != "supporting" and existing.role_type == "supporting":
                existing.role_type = role_type
            existing.updated_at = datetime.now()
            self.db.commit()
            return existing
        
        # 创建新记录
        character = Character(
            edition_id=edition_id,
            canonical_name=canonical_name,
            role_type=role_type,
            description=description,
            source=source,
            status="draft",
        )
        self.db.add(character)
        self.db.commit()
        
        return character
    
    def _add_alias(
        self,
        character_id: int,
        alias: str,
        alias_type: str = "other",
        source: str = "manual",
    ) -> Optional[CharacterAlias]:
        """添加人物别名"""
        if not alias:
            return None
        
        # 检查是否已存在
        existing = self.db.query(CharacterAlias).filter(
            CharacterAlias.character_id == character_id,
            CharacterAlias.alias == alias,
        ).first()
        
        if existing:
            return existing
        
        alias_obj = CharacterAlias(
            character_id=character_id,
            alias=alias,
            alias_type=alias_type,
            source=source,
        )
        self.db.add(alias_obj)
        self.db.commit()
        
        return alias_obj
    
    def _add_attribute(
        self,
        character_id: int,
        category: str,
        key: str,
        value: str,
        confidence: Optional[float] = None,
        source: str = "manual",
    ) -> Optional[CharacterAttribute]:
        """添加人物属性"""
        if not key or not value:
            return None
        
        # 检查是否已存在相同类别和键的属性
        existing = self.db.query(CharacterAttribute).filter(
            CharacterAttribute.character_id == character_id,
            CharacterAttribute.category == category,
            CharacterAttribute.attr_key == key,
        ).first()
        
        if existing:
            # 如果新属性置信度更高，更新它
            if confidence and (not existing.confidence or confidence > existing.confidence):
                existing.attr_value = value
                existing.confidence = confidence
                existing.source = source
                existing.updated_at = datetime.now()
                self.db.commit()
            return existing
        
        attr = CharacterAttribute(
            character_id=character_id,
            category=category,
            attr_key=key,
            attr_value=value,
            confidence=confidence,
            source=source,
            status="pending",
        )
        self.db.add(attr)
        self.db.commit()
        
        return attr
    
    def _calculate_character_similarity(
        self,
        char1: Character,
        char2: Character,
    ) -> Tuple[float, str]:
        """计算两个人物的相似度
        
        Returns:
            (相似度分数, 原因描述)
        """
        reasons = []
        
        # 1. 名称相似度
        name_sim = SequenceMatcher(None, char1.canonical_name, char2.canonical_name).ratio()
        if name_sim >= self.NAME_SIMILARITY_THRESHOLD:
            reasons.append(f"名称高度相似 ({name_sim:.2f})")
        
        # 2. 别名匹配
        aliases1 = {a.alias for a in char1.aliases}
        aliases2 = {a.alias for a in char2.aliases}
        
        # 检查是否有别名互相包含
        if char1.canonical_name in aliases2:
            reasons.append(f"'{char1.canonical_name}' 是 '{char2.canonical_name}' 的别名")
            name_sim = max(name_sim, 0.95)
        if char2.canonical_name in aliases1:
            reasons.append(f"'{char2.canonical_name}' 是 '{char1.canonical_name}' 的别名")
            name_sim = max(name_sim, 0.95)
        
        # 检查别名交集
        common_aliases = aliases1 & aliases2
        if common_aliases:
            reasons.append(f"共同别名: {', '.join(common_aliases)}")
            name_sim = max(name_sim, 0.9)
        
        # 3. 综合相似度
        final_score = name_sim
        
        return final_score, "; ".join(reasons) if reasons else "无显著相似性"
    
    def _merge_aliases(self, target: Character, source: Character):
        """合并别名"""
        target_aliases = {a.alias for a in target.aliases}
        
        for alias in source.aliases:
            if alias.alias not in target_aliases:
                new_alias = CharacterAlias(
                    character_id=target.id,
                    alias=alias.alias,
                    alias_type=alias.alias_type,
                    source=alias.source,
                )
                self.db.add(new_alias)
        
        self.db.commit()
    
    def _merge_attributes(
        self,
        target: Character,
        source: Character,
        strategy: str = "smart",
    ):
        """合并属性"""
        target_attrs = {
            (a.category, a.attr_key): a
            for a in target.attributes
        }
        
        for attr in source.attributes:
            key = (attr.category, attr.attr_key)
            
            if key not in target_attrs:
                # 目标没有此属性，直接添加
                new_attr = CharacterAttribute(
                    character_id=target.id,
                    category=attr.category,
                    attr_key=attr.attr_key,
                    attr_value=attr.attr_value,
                    confidence=attr.confidence,
                    source=attr.source,
                    status=attr.status,
                )
                self.db.add(new_attr)
            elif strategy == "smart":
                # 智能合并：保留置信度更高的
                existing = target_attrs[key]
                if attr.confidence and (not existing.confidence or attr.confidence > existing.confidence):
                    existing.attr_value = attr.attr_value
                    existing.confidence = attr.confidence
                    existing.updated_at = datetime.now()
        
        self.db.commit()
    
    def _migrate_relations(self, target: Character, source: Character):
        """迁移关系到目标人物"""
        # 更新以 source 为起点的关系
        source_relations = self.db.query(CharacterRelation).filter(
            CharacterRelation.source_character_id == source.id
        ).all()
        
        for rel in source_relations:
            # 检查是否已存在相同关系
            existing = self.db.query(CharacterRelation).filter(
                CharacterRelation.source_character_id == target.id,
                CharacterRelation.target_character_id == rel.target_character_id,
                CharacterRelation.relation_type == rel.relation_type,
            ).first()
            
            if not existing:
                rel.source_character_id = target.id
        
        # 更新以 source 为终点的关系
        target_relations = self.db.query(CharacterRelation).filter(
            CharacterRelation.target_character_id == source.id
        ).all()
        
        for rel in target_relations:
            existing = self.db.query(CharacterRelation).filter(
                CharacterRelation.source_character_id == rel.source_character_id,
                CharacterRelation.target_character_id == target.id,
                CharacterRelation.relation_type == rel.relation_type,
            ).first()
            
            if not existing:
                rel.target_character_id = target.id
        
        self.db.commit()
    
    def _build_character_profile(self, character_id: int) -> CharacterProfile:
        """构建人物档案"""
        character = self.db.query(Character).get(character_id)
        
        if not character:
            raise ValueError(f"Character {character_id} not found")
        
        # 转换为 DTO
        char_data = CharacterData.read_from_orm(character)
        
        aliases = [
            CharacterAliasData.read_from_orm(a)
            for a in character.aliases
        ]
        
        attributes = [
            CharacterAttributeData.read_from_orm(a)
            for a in character.attributes
        ]
        
        # 获取关系
        relations = []
        for rel in character.source_relations:
            relations.append(CharacterRelationData.read_from_orm(rel))
        for rel in character.target_relations:
            if not rel.is_mutual:
                relations.append(CharacterRelationData.read_from_orm(rel))
        
        # 获取弧光（如果有）
        arcs = []  # TODO: 实现弧光查询
        
        return CharacterProfile(
            character=char_data,
            aliases=aliases,
            attributes=attributes,
            arcs=arcs,
            relations=relations,
        )


# ============================================================================
# Convenience Functions
# ============================================================================

def deduplicate_characters(
    db: Session,
    edition_id: int,
    auto_merge_threshold: float = 0.85,
) -> Dict[str, Any]:
    """便捷函数：对版本人物进行去重
    
    Args:
        db: 数据库会话
        edition_id: 版本ID
        auto_merge_threshold: 自动合并阈值
        
    Returns:
        去重结果统计
    """
    profiler = CharacterProfiler(db)
    return profiler.auto_merge_duplicates(edition_id, auto_merge_threshold)


def merge_character_pair(
    db: Session,
    target_character_id: int,
    source_character_id: int,
) -> Optional[Character]:
    """便捷函数：合并两个人物
    
    Args:
        db: 数据库会话
        target_character_id: 保留的目标人物ID
        source_character_id: 被合并的源人物ID
        
    Returns:
        合并后的人物
    """
    profiler = CharacterProfiler(db)
    return profiler.merge_characters(target_character_id, source_character_id)
