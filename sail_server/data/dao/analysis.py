# -*- coding: utf-8 -*-
# @file analysis.py
# @brief Analysis DAO
# @author sailing-innocent
# @date 2026-03-01
# @version 1.0
# ---------------------------------

"""
分析模块 DAO

从 sail_server/model/analysis/ 迁移数据访问逻辑
"""

from typing import List, Optional, Dict, Any
from sqlalchemy import func
from sqlalchemy.orm import Session

from sail_server.infrastructure.orm.analysis import (
    Character, CharacterAlias, CharacterAttribute, CharacterRelation,
    Outline, OutlineNode, OutlineEvent,
    Setting, SettingAttribute,
    TextEvidence,
)
from sail_server.data.dao.base import BaseDAO


# ============================================================================
# Character DAO
# ============================================================================

class CharacterDAO(BaseDAO[Character]):
    """人物 DAO"""
    
    def __init__(self, db: Session):
        super().__init__(db, Character)
    
    def get_by_edition(
        self,
        edition_id: int,
        role_type: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[Character]:
        """获取版本的所有人物"""
        query = self.db.query(Character).filter(Character.edition_id == edition_id)
        
        if role_type:
            query = query.filter(Character.role_type == role_type)
        if status:
            query = query.filter(Character.status == status)
        
        return query.order_by(
            Character.importance_score.desc(),
            Character.canonical_name
        ).all()
    
    def get_with_relations(self, character_id: int) -> Optional[Character]:
        """获取人物及其关联数据"""
        character = self.get_by_id(character_id)
        if character:
            # 触发加载关联
            _ = character.aliases
            _ = character.attributes
            _ = character.arcs
        return character
    
    def search_by_name(self, edition_id: int, name: str) -> List[Character]:
        """按名称搜索人物"""
        return self.db.query(Character).filter(
            Character.edition_id == edition_id,
            Character.canonical_name.ilike(f"%{name}%")
        ).all()


class CharacterAliasDAO(BaseDAO[CharacterAlias]):
    """人物别名 DAO"""
    
    def __init__(self, db: Session):
        super().__init__(db, CharacterAlias)
    
    def get_by_character(self, character_id: int) -> List[CharacterAlias]:
        """获取人物的所有别名"""
        return self.db.query(CharacterAlias).filter(
            CharacterAlias.character_id == character_id
        ).all()


class CharacterAttributeDAO(BaseDAO[CharacterAttribute]):
    """人物属性 DAO"""
    
    def __init__(self, db: Session):
        super().__init__(db, CharacterAttribute)
    
    def get_by_character(self, character_id: int) -> List[CharacterAttribute]:
        """获取人物的所有属性"""
        return self.db.query(CharacterAttribute).filter(
            CharacterAttribute.character_id == character_id
        ).all()


# ============================================================================
# Outline DAO
# ============================================================================

class OutlineDAO(BaseDAO[Outline]):
    """大纲 DAO"""
    
    def __init__(self, db: Session):
        super().__init__(db, Outline)
    
    def get_by_edition(self, edition_id: int) -> List[Outline]:
        """获取版本的所有大纲"""
        return self.db.query(Outline).filter(
            Outline.edition_id == edition_id
        ).order_by(Outline.created_at.desc()).all()
    
    def get_with_nodes(self, outline_id: int) -> Optional[Outline]:
        """获取大纲及其所有节点"""
        outline = self.get_by_id(outline_id)
        if outline:
            _ = outline.nodes
        return outline


class OutlineNodeDAO(BaseDAO[OutlineNode]):
    """大纲节点 DAO"""
    
    def __init__(self, db: Session):
        super().__init__(db, OutlineNode)
    
    def get_by_outline(self, outline_id: int) -> List[OutlineNode]:
        """获取大纲的所有节点"""
        return self.db.query(OutlineNode).filter(
            OutlineNode.outline_id == outline_id
        ).order_by(OutlineNode.sort_index).all()
    
    def get_children(self, node_id: int) -> List[OutlineNode]:
        """获取节点的子节点"""
        return self.db.query(OutlineNode).filter(
            OutlineNode.parent_id == node_id
        ).order_by(OutlineNode.sort_index).all()


class OutlineEventDAO(BaseDAO[OutlineEvent]):
    """大纲事件 DAO"""
    
    def __init__(self, db: Session):
        super().__init__(db, OutlineEvent)
    
    def get_by_node(self, node_id: int) -> List[OutlineEvent]:
        """获取节点的所有事件"""
        return self.db.query(OutlineEvent).filter(
            OutlineEvent.outline_node_id == node_id
        ).order_by(OutlineEvent.narrative_order).all()


# ============================================================================
# Setting DAO
# ============================================================================

class SettingDAO(BaseDAO[Setting]):
    """设定 DAO"""
    
    def __init__(self, db: Session):
        super().__init__(db, Setting)
    
    def get_by_edition(
        self,
        edition_id: int,
        setting_type: Optional[str] = None
    ) -> List[Setting]:
        """获取版本的所有设定"""
        query = self.db.query(Setting).filter(Setting.edition_id == edition_id)
        
        if setting_type:
            query = query.filter(Setting.setting_type == setting_type)
        
        return query.order_by(Setting.canonical_name).all()
    
    def search_by_name(self, edition_id: int, name: str) -> List[Setting]:
        """按名称搜索设定"""
        return self.db.query(Setting).filter(
            Setting.edition_id == edition_id,
            Setting.canonical_name.ilike(f"%{name}%")
        ).all()


class SettingAttributeDAO(BaseDAO[SettingAttribute]):
    """设定属性 DAO"""
    
    def __init__(self, db: Session):
        super().__init__(db, SettingAttribute)
    
    def get_by_setting(self, setting_id: int) -> List[SettingAttribute]:
        """获取设定的所有属性"""
        return self.db.query(SettingAttribute).filter(
            SettingAttribute.setting_id == setting_id
        ).all()


# ============================================================================
# Evidence DAO
# ============================================================================

class TextEvidenceDAO(BaseDAO[TextEvidence]):
    """文本证据 DAO"""
    
    def __init__(self, db: Session):
        super().__init__(db, TextEvidence)
    
    def get_by_edition(self, edition_id: int) -> List[TextEvidence]:
        """获取版本的所有证据"""
        return self.db.query(TextEvidence).filter(
            TextEvidence.edition_id == edition_id
        ).order_by(TextEvidence.created_at.desc()).all()
    
    def get_by_node(self, node_id: int) -> List[TextEvidence]:
        """获取节点的所有证据"""
        return self.db.query(TextEvidence).filter(
            TextEvidence.node_id == node_id
        ).order_by(TextEvidence.start_char).all()
    
    def get_by_target(
        self,
        target_type: str,
        target_id: int
    ) -> List[TextEvidence]:
        """获取目标的所有证据"""
        return self.db.query(TextEvidence).filter(
            TextEvidence.target_type == target_type,
            TextEvidence.target_id == target_id
        ).order_by(TextEvidence.created_at.desc()).all()
    
    def get_by_edition_and_target_type(
        self,
        edition_id: int,
        target_type: str
    ) -> List[TextEvidence]:
        """获取版本中特定类型的所有证据"""
        return self.db.query(TextEvidence).filter(
            TextEvidence.edition_id == edition_id,
            TextEvidence.target_type == target_type
        ).order_by(TextEvidence.created_at.desc()).all()
    
    def count_by_target_type(self, edition_id: int) -> Dict[str, int]:
        """统计各目标类型的证据数量"""
        results = self.db.query(
            TextEvidence.target_type,
            func.count(TextEvidence.id)
        ).filter(
            TextEvidence.edition_id == edition_id
        ).group_by(TextEvidence.target_type).all()
        
        return {target_type: count for target_type, count in results}
