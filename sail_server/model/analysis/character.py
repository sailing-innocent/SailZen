# -*- coding: utf-8 -*-
# @file character.py
# @brief Character Management Business Logic
# @author sailing-innocent
# @date 2025-03-01
# @version 1.0
# ---------------------------------

from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func

from sail_server.data.analysis import (
    Character, CharacterData,
    CharacterAlias, CharacterAliasData,
    CharacterAttribute, CharacterAttributeData,
    CharacterRelation, CharacterRelationData,
)


# ============================================================================
# Character CRUD Operations
# ============================================================================

def create_character_impl(db: Session, data: CharacterData) -> CharacterData:
    """创建人物"""
    character = data.create_orm()
    db.add(character)
    db.commit()
    db.refresh(character)
    return CharacterData.read_from_orm(character)


def get_character_impl(db: Session, character_id: int) -> Optional[CharacterData]:
    """获取单个人物"""
    character = db.query(Character).filter(Character.id == character_id).first()
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
    query = db.query(Character).filter(Character.edition_id == edition_id)
    
    if role_type:
        query = query.filter(Character.role_type == role_type)
    if status:
        query = query.filter(Character.status == status)
    
    characters = query.order_by(Character.importance_score.desc(), Character.canonical_name).all()
    return [CharacterData.read_from_orm(c) for c in characters]


def update_character_impl(
    db: Session, 
    character_id: int, 
    data: Dict[str, Any]
) -> Optional[CharacterData]:
    """更新人物"""
    character = db.query(Character).filter(Character.id == character_id).first()
    if not character:
        return None
    
    # 更新字段
    for key, value in data.items():
        if hasattr(character, key) and value is not None:
            setattr(character, key, value)
    
    db.commit()
    db.refresh(character)
    return CharacterData.read_from_orm(character)


def delete_character_impl(db: Session, character_id: int) -> bool:
    """删除人物"""
    character = db.query(Character).filter(Character.id == character_id).first()
    if not character:
        return False
    
    db.delete(character)
    db.commit()
    return True


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
    alias_obj = CharacterAlias(
        character_id=character_id,
        alias=alias,
        alias_type=alias_type,
        usage_context=usage_context,
        is_preferred=is_preferred,
    )
    db.add(alias_obj)
    db.commit()
    db.refresh(alias_obj)
    return CharacterAliasData.read_from_orm(alias_obj)


def remove_character_alias_impl(db: Session, alias_id: int) -> bool:
    """删除人物别名"""
    alias = db.query(CharacterAlias).filter(CharacterAlias.id == alias_id).first()
    if not alias:
        return False
    
    db.delete(alias)
    db.commit()
    return True


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
    # 检查是否已存在相同 key 的属性
    existing = db.query(CharacterAttribute).filter(
        CharacterAttribute.character_id == character_id,
        CharacterAttribute.attr_key == attr_key
    ).first()
    
    if existing:
        # 更新现有属性
        existing.attr_value = attr_value
        existing.category = category
        existing.confidence = confidence
        existing.source_node_id = source_node_id
        db.commit()
        db.refresh(existing)
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
    db.add(attr)
    db.commit()
    db.refresh(attr)
    return CharacterAttributeData.read_from_orm(attr)


def delete_character_attribute_impl(db: Session, attribute_id: int) -> bool:
    """删除人物属性"""
    attr = db.query(CharacterAttribute).filter(CharacterAttribute.id == attribute_id).first()
    if not attr:
        return False
    
    db.delete(attr)
    db.commit()
    return True


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
