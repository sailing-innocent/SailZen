# -*- coding: utf-8 -*-
# @file entity_linker.py
# @brief Entity Linking Service - Link extracted entities to existing Character ORM
# @author sailing-innocent
# @date 2026-04-17
# @version 1.0
# ---------------------------------

"""
实体链接服务

将大纲提取过程中发现的候选实体与现有 Character / Setting ORM 进行关联：
1. 名称精确匹配 → 已有 Character
2. 模糊匹配 → LLM 消歧
3. 无匹配 → 创建新 Character
"""

import logging
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

from sqlalchemy.orm import Session

from sail_server.infrastructure.orm.analysis import (
    Character,
    CharacterAlias,
    CharacterAttribute,
)
from sail_server.data.dao import CharacterDAO, CharacterAliasDAO

logger = logging.getLogger(__name__)


# ============================================================================
# Linking Result Types
# ============================================================================

class LinkAction(str, Enum):
    """链接动作"""
    MATCHED = "matched"          # 精确匹配已有实体
    ALIAS_MATCHED = "alias_matched"  # 匹配到别名
    FUZZY_MATCHED = "fuzzy_matched"  # 模糊匹配（需 LLM 确认）
    NEW = "new"                  # 新建实体
    UNCERTAIN = "uncertain"      # 不确定（待人工审核）


@dataclass
class EntityLinkResult:
    """实体链接结果"""
    candidate_name: str
    action: LinkAction
    character_id: Optional[int] = None
    confidence: float = 0.0
    reason: str = ""
    suggested_aliases: List[str] = field(default_factory=list)


# ============================================================================
# Entity Linker
# ============================================================================

class EntityLinker:
    """实体链接器
    
    将提取的候选实体名称链接到数据库中的 Character 记录。
    """
    
    # 置信度阈值
    EXACT_MATCH_THRESHOLD = 1.0
    ALIAS_MATCH_THRESHOLD = 0.95
    FUZZY_MATCH_THRESHOLD = 0.7
    UNCERTAIN_THRESHOLD = 0.4
    
    def __init__(self, db: Session):
        self.db = db
        self.character_dao = CharacterDAO(db)
        self.alias_dao = CharacterAliasDAO(db)
    
    def link_entities(
        self,
        edition_id: int,
        candidate_names: List[str],
    ) -> List[EntityLinkResult]:
        """链接候选实体到现有 Character 表
        
        Args:
            edition_id: 版本 ID
            candidate_names: 候选实体名称列表（从大纲提取结果中获得）
            
        Returns:
            链接结果列表
        """
        # 加载该版本的所有角色和别名
        characters = self.character_dao.get_by_edition(edition_id)
        aliases = self._load_all_aliases(edition_id)
        
        results = []
        for name in candidate_names:
            result = self._link_single_entity(name, characters, aliases)
            results.append(result)
        
        logger.info(f"[EntityLinker] Linked {len(candidate_names)} entities: "
                   f"{sum(1 for r in results if r.action == LinkAction.MATCHED)} exact, "
                   f"{sum(1 for r in results if r.action == LinkAction.ALIAS_MATCHED)} alias, "
                   f"{sum(1 for r in results if r.action == LinkAction.NEW)} new")
        
        return results
    
    def _link_single_entity(
        self,
        name: str,
        characters: List[Character],
        aliases: Dict[str, List[Tuple[int, str]]],  # alias -> [(character_id, alias_type), ...]
    ) -> EntityLinkResult:
        """链接单个实体"""
        name_clean = name.strip()
        if not name_clean:
            return EntityLinkResult(
                candidate_name=name,
                action=LinkAction.UNCERTAIN,
                confidence=0.0,
                reason="空名称",
            )
        
        # 1. 精确匹配规范名
        for char in characters:
            if char.canonical_name == name_clean:
                return EntityLinkResult(
                    candidate_name=name,
                    action=LinkAction.MATCHED,
                    character_id=char.id,
                    confidence=1.0,
                    reason=f"精确匹配规范名: {char.canonical_name}",
                )
        
        # 2. 精确匹配别名
        if name_clean in aliases:
            matches = aliases[name_clean]
            if matches:
                char_id, alias_type = matches[0]
                return EntityLinkResult(
                    candidate_name=name,
                    action=LinkAction.ALIAS_MATCHED,
                    character_id=char_id,
                    confidence=0.95,
                    reason=f"匹配别名 ({alias_type}): {name_clean}",
                )
        
        # 3. 模糊匹配（简单实现：包含关系）
        for char in characters:
            # 名称包含关系
            if name_clean in char.canonical_name or char.canonical_name in name_clean:
                similarity = self._calculate_similarity(name_clean, char.canonical_name)
                if similarity >= self.FUZZY_MATCH_THRESHOLD:
                    return EntityLinkResult(
                        candidate_name=name,
                        action=LinkAction.FUZZY_MATCHED,
                        character_id=char.id,
                        confidence=similarity,
                        reason=f"模糊匹配: '{name_clean}' ~ '{char.canonical_name}'",
                        suggested_aliases=[name_clean] if name_clean != char.canonical_name else [],
                    )
            
            # 检查别名
            for alias_record in char.aliases:
                alias_name = alias_record.alias
                if name_clean in alias_name or alias_name in name_clean:
                    similarity = self._calculate_similarity(name_clean, alias_name)
                    if similarity >= self.FUZZY_MATCH_THRESHOLD:
                        return EntityLinkResult(
                            candidate_name=name,
                            action=LinkAction.FUZZY_MATCHED,
                            character_id=char.id,
                            confidence=similarity,
                            reason=f"模糊匹配别名: '{name_clean}' ~ '{alias_name}'",
                            suggested_aliases=[name_clean] if name_clean != char.canonical_name else [],
                        )
        
        # 4. 无匹配，标记为新实体
        return EntityLinkResult(
            candidate_name=name,
            action=LinkAction.NEW,
            confidence=0.0,
            reason="未找到匹配，建议创建新实体",
        )
    
    def apply_links(
        self,
        edition_id: int,
        link_results: List[EntityLinkResult],
    ) -> Dict[str, Any]:
        """应用链接结果到数据库
        
        Args:
            edition_id: 版本 ID
            link_results: 链接结果列表
            
        Returns:
            操作统计
        """
        stats = {
            "matched": 0,
            "alias_added": 0,
            "new_created": 0,
            "uncertain": 0,
            "errors": [],
        }
        
        for result in link_results:
            try:
                if result.action in (LinkAction.MATCHED, LinkAction.ALIAS_MATCHED):
                    stats["matched"] += 1
                    
                elif result.action == LinkAction.FUZZY_MATCHED:
                    # 添加为新别名
                    if result.suggested_aliases and result.character_id:
                        for alias in result.suggested_aliases:
                            self._add_alias_safely(
                                character_id=result.character_id,
                                alias=alias,
                                alias_type="nickname",
                                usage_context=f"AI提取发现，置信度 {result.confidence:.2f}",
                            )
                        stats["alias_added"] += 1
                        stats["matched"] += 1
                    else:
                        stats["uncertain"] += 1
                        
                elif result.action == LinkAction.NEW:
                    # 创建新角色
                    new_char = self._create_character_safely(
                        edition_id=edition_id,
                        name=result.candidate_name,
                        source="ai_extraction",
                    )
                    if new_char:
                        stats["new_created"] += 1
                    else:
                        stats["uncertain"] += 1
                        
                elif result.action == LinkAction.UNCERTAIN:
                    stats["uncertain"] += 1
                    
            except Exception as e:
                logger.error(f"[EntityLinker] Failed to apply link for {result.candidate_name}: {e}")
                stats["errors"].append({"name": result.candidate_name, "error": str(e)})
        
        return stats
    
    def _load_all_aliases(self, edition_id: int) -> Dict[str, List[Tuple[int, str]]]:
        """加载版本的所有别名"""
        alias_map: Dict[str, List[Tuple[int, str]]] = {}
        
        # 查询该版本的所有角色别名
        aliases = self.db.query(CharacterAlias).join(Character).filter(
            Character.edition_id == edition_id
        ).all()
        
        for alias in aliases:
            name = alias.alias.strip()
            if name not in alias_map:
                alias_map[name] = []
            alias_map[name].append((alias.character_id, alias.alias_type or "nickname"))
        
        return alias_map
    
    def _calculate_similarity(self, s1: str, s2: str) -> float:
        """计算字符串相似度（Jaccard）"""
        if s1 == s2:
            return 1.0
        if not s1 or not s2:
            return 0.0
        
        set1 = set(s1)
        set2 = set(s2)
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        return intersection / union if union > 0 else 0.0
    
    def _add_alias_safely(
        self,
        character_id: int,
        alias: str,
        alias_type: str = "nickname",
        usage_context: Optional[str] = None,
    ) -> bool:
        """安全地添加别名（避免重复）"""
        try:
            # 检查是否已存在
            existing = self.db.query(CharacterAlias).filter(
                CharacterAlias.character_id == character_id,
                CharacterAlias.alias == alias,
            ).first()
            
            if existing:
                return True  # 已存在，视为成功
            
            new_alias = CharacterAlias(
                character_id=character_id,
                alias=alias,
                alias_type=alias_type,
                usage_context=usage_context,
                source="ai_extraction",
            )
            self.db.add(new_alias)
            self.db.commit()
            return True
            
        except Exception as e:
            logger.error(f"[EntityLinker] Failed to add alias: {e}")
            self.db.rollback()
            return False
    
    def _create_character_safely(
        self,
        edition_id: int,
        name: str,
        source: str = "ai_extraction",
    ) -> Optional[Character]:
        """安全地创建角色（避免重复）"""
        try:
            # 检查是否已存在
            existing = self.db.query(Character).filter(
                Character.edition_id == edition_id,
                Character.canonical_name == name,
            ).first()
            
            if existing:
                return existing
            
            character = Character(
                edition_id=edition_id,
                canonical_name=name,
                role_type="supporting",
                source=source,
                status="draft",
            )
            self.db.add(character)
            self.db.commit()
            self.db.refresh(character)
            return character
            
        except Exception as e:
            logger.error(f"[EntityLinker] Failed to create character: {e}")
            self.db.rollback()
            return None


# ============================================================================
# Export
# ============================================================================

__all__ = [
    "LinkAction",
    "EntityLinkResult",
    "EntityLinker",
]
