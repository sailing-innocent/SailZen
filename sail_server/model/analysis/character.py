# -*- coding: utf-8 -*-
# @file character.py
# @brief Character Management Business Logic
# @author sailing-innocent
# @date 2025-03-01
# @version 1.0
# ---------------------------------

from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

# 使用新的 DAO 层（Phase 4）
from sail_server.data.dao import (
    CharacterDAO, CharacterAliasDAO, CharacterAttributeDAO,
)
from sail_server.infrastructure.orm import (
    Character, CharacterAlias, CharacterAttribute,
)

# 保留 dataclass DTO 导入（Phase 3 Pydantic DTO 迁移后替换）
from sail_server.data.analysis import (
    CharacterData, CharacterAliasData, CharacterAttributeData, CharacterRelationData,
)


# ============================================================================
# Character CRUD Operations
# ============================================================================

def create_character_impl(db: Session, data: CharacterData) -> CharacterData:
    """创建人物"""
    # Phase 4: 使用 DAO 层
    character_dao = CharacterDAO(db)
    character = character_dao.create(data.create_orm())
    return CharacterData.read_from_orm(character)


def get_character_impl(db: Session, character_id: int) -> Optional[CharacterData]:
    """获取单个人物"""
    # Phase 4: 使用 DAO 层
    character_dao = CharacterDAO(db)
    character = character_dao.get_by_id(character_id)
    if not character:
        return None
    return CharacterData.read_from_orm(character)


def get_characters_by_edition_impl(
    db: Session, 
    edition_id: int,
    role_type: Optional[str] = None,
    status: Optional[str] = None
) -> List[CharacterData]:
    """获取版本的所有人物"""
    # Phase 4: 使用 DAO 层
    character_dao = CharacterDAO(db)
    characters = character_dao.get_by_edition(edition_id, role_type, status)
    return [CharacterData.read_from_orm(c) for c in characters]


def update_character_impl(
    db: Session, 
    character_id: int, 
    data: Dict[str, Any]
) -> Optional[CharacterData]:
    """更新人物"""
    # Phase 4: 使用 DAO 层
    character_dao = CharacterDAO(db)
    character = character_dao.update(character_id, data)
    if not character:
        return None
    return CharacterData.read_from_orm(character)


def delete_character_impl(db: Session, character_id: int) -> bool:
    """删除人物"""
    # Phase 4: 使用 DAO 层
    character_dao = CharacterDAO(db)
    return character_dao.delete(character_id)


# ============================================================================
# Character Alias Operations
# ============================================================================

def add_character_alias_impl(
    db: Session,
    character_id: int,
    alias: str,
    alias_type: str = "nickname",
    usage_context: Optional[str] = None,
    is_preferred: bool = False
) -> CharacterAliasData:
    """添加人物别名"""
    # Phase 4: 使用 DAO 层
    alias_dao = CharacterAliasDAO(db)
    alias_obj = CharacterAlias(
        character_id=character_id,
        alias=alias,
        alias_type=alias_type,
        usage_context=usage_context,
        is_preferred=is_preferred,
    )
    alias_obj = alias_dao.create(alias_obj)
    return CharacterAliasData.read_from_orm(alias_obj)


def remove_character_alias_impl(db: Session, alias_id: int) -> bool:
    """删除人物别名"""
    # Phase 4: 使用 DAO 层
    alias_dao = CharacterAliasDAO(db)
    return alias_dao.delete(alias_id)


# ============================================================================
# Character Attribute Operations
# ============================================================================

def add_character_attribute_impl(
    db: Session,
    character_id: int,
    attr_key: str,
    attr_value: str,
    category: Optional[str] = None,
    confidence: Optional[float] = None,
    source_node_id: Optional[int] = None,
) -> CharacterAttributeData:
    """添加人物属性"""
    # Phase 4: 使用 DAO 层
    attr_dao = CharacterAttributeDAO(db)
    
    # 检查是否已存在相同 key 的属性
    existing = db.query(CharacterAttribute).filter(
        CharacterAttribute.character_id == character_id,
        CharacterAttribute.attr_key == attr_key
    ).first()
    
    if existing:
        # 更新现有属性
        existing = attr_dao.update(existing.id, {
            "attr_value": attr_value,
            "category": category,
            "confidence": confidence,
            "source_node_id": source_node_id,
        })
        return CharacterAttributeData.read_from_orm(existing)
    
    # 创建新属性
    attr = CharacterAttribute(
        character_id=character_id,
        category=category,
        attr_key=attr_key,
        attr_value=attr_value,
        confidence=confidence,
        source_node_id=source_node_id,
    )
    attr = attr_dao.create(attr)
    return CharacterAttributeData.read_from_orm(attr)


def delete_character_attribute_impl(db: Session, attribute_id: int) -> bool:
    """删除人物属性"""
    # Phase 4: 使用 DAO 层
    attr_dao = CharacterAttributeDAO(db)
    return attr_dao.delete(attribute_id)


# ============================================================================
# Character Relation Operations
# ============================================================================

def add_character_relation_impl(
    db: Session,
    edition_id: int,
    source_character_id: int,
    target_character_id: int,
    relation_type: str,
    relation_subtype: Optional[str] = None,
    description: Optional[str] = None,
    strength: Optional[float] = None,
    is_mutual: bool = True,
) -> CharacterRelationData:
    """添加人物关系"""
    relation = CharacterRelation(
        edition_id=edition_id,
        source_character_id=source_character_id,
        target_character_id=target_character_id,
        relation_type=relation_type,
        relation_subtype=relation_subtype,
        description=description,
        strength=strength,
        is_mutual=is_mutual,
    )
    db.add(relation)
    db.commit()
    db.refresh(relation)
    return CharacterRelationData.read_from_orm(relation)


def get_character_relations_impl(
    db: Session,
    character_id: int,
    relation_type: Optional[str] = None
) -> List[CharacterRelationData]:
    """获取人物的所有关系"""
    query = db.query(CharacterRelation).filter(
        (CharacterRelation.source_character_id == character_id) |
        (CharacterRelation.target_character_id == character_id)
    )
    
    if relation_type:
        query = query.filter(CharacterRelation.relation_type == relation_type)
    
    relations = query.all()
    return [CharacterRelationData.read_from_orm(r) for r in relations]


def delete_character_relation_impl(db: Session, relation_id: int) -> bool:
    """删除人物关系"""
    relation = db.query(CharacterRelation).filter(CharacterRelation.id == relation_id).first()
    if not relation:
        return False
    
    db.delete(relation)
    db.commit()
    return True


def get_character_profile_impl(db: Session, character_id: int) -> Optional[Dict[str, Any]]:
    """获取人物档案"""
    character = db.query(Character).filter(Character.id == character_id).first()
    if not character:
        return None
    
    # 构建档案数据
    profile = {
        "character": CharacterData.read_from_orm(character),
        "aliases": [CharacterAliasData.read_from_orm(a) for a in character.aliases],
        "attributes": [CharacterAttributeData.read_from_orm(a) for a in character.attributes],
        "arcs": [],  # TODO: 实现人物弧线
        "relations": [],  # TODO: 实现关系查询
    }
    
    return profile
