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
from sail_server.infrastructure.orm.analysis import (
    Character, CharacterAlias, CharacterAttribute, CharacterRelation,
)

# 使用 Pydantic DTOs
from sail_server.application.dto.analysis import (
    CharacterResponse, CharacterCreateRequest,
)


# ============================================================================
# Helper Functions for ORM to DTO Conversion
# ============================================================================

def _character_to_response(character: Character) -> CharacterResponse:
    """将 Character ORM 对象转换为 CharacterResponse DTO"""
    return CharacterResponse(
        id=character.id,
        edition_id=character.edition_id,
        canonical_name=character.canonical_name,
        role_type=character.role_type or "supporting",
        description=character.description,
        first_appearance_node_id=character.first_appearance_node_id,
        status=character.status or "draft",
        source=character.source or "manual",
        importance_score=character.importance_score,
        created_at=character.created_at,
        updated_at=character.updated_at,
    )


def _alias_to_dict(alias: CharacterAlias) -> Dict[str, Any]:
    """将 CharacterAlias ORM 对象转换为字典"""
    return {
        "id": alias.id,
        "character_id": alias.character_id,
        "alias": alias.alias,
        "alias_type": alias.alias_type,
        "usage_context": alias.usage_context,
        "is_preferred": alias.is_preferred,
        "source": alias.source,
        "created_at": alias.created_at,
    }


def _attribute_to_dict(attr: CharacterAttribute) -> Dict[str, Any]:
    """将 CharacterAttribute ORM 对象转换为字典"""
    return {
        "id": attr.id,
        "character_id": attr.character_id,
        "category": attr.category,
        "attr_key": attr.attr_key,
        "attr_value": attr.attr_value,
        "confidence": attr.confidence,
        "source": attr.source,
        "source_node_id": attr.source_node_id,
        "status": attr.status,
        "created_at": attr.created_at,
        "updated_at": attr.updated_at,
    }


def _relation_to_dict(relation: CharacterRelation) -> Dict[str, Any]:
    """将 CharacterRelation ORM 对象转换为字典"""
    return {
        "id": relation.id,
        "edition_id": relation.edition_id,
        "source_character_id": relation.source_character_id,
        "target_character_id": relation.target_character_id,
        "relation_type": relation.relation_type,
        "relation_subtype": relation.relation_subtype,
        "description": relation.description,
        "strength": relation.strength,
        "is_mutual": relation.is_mutual,
        "status": relation.status,
        "created_at": relation.created_at,
        "updated_at": relation.updated_at,
    }


# ============================================================================
# Character CRUD Operations
# ============================================================================

def create_character_impl(db: Session, data: CharacterCreateRequest) -> CharacterResponse:
    """创建人物"""
    # Phase 4: 使用 DAO 层
    character_dao = CharacterDAO(db)
    character = Character(
        edition_id=data.edition_id,
        canonical_name=data.canonical_name,
        role_type=data.role_type,
        description=data.description,
        source="manual",
    )
    character = character_dao.create(character)
    return _character_to_response(character)


def get_character_impl(db: Session, character_id: int) -> Optional[CharacterResponse]:
    """获取单个人物"""
    # Phase 4: 使用 DAO 层
    character_dao = CharacterDAO(db)
    character = character_dao.get_by_id(character_id)
    if not character:
        return None
    return _character_to_response(character)


def get_characters_by_edition_impl(
    db: Session, 
    edition_id: int,
    role_type: Optional[str] = None,
    status: Optional[str] = None
) -> List[CharacterResponse]:
    """获取版本的所有人物"""
    # Phase 4: 使用 DAO 层
    character_dao = CharacterDAO(db)
    characters = character_dao.get_by_edition(edition_id, role_type, status)
    return [_character_to_response(c) for c in characters]


def update_character_impl(
    db: Session, 
    character_id: int, 
    data: Dict[str, Any]
) -> Optional[CharacterResponse]:
    """更新人物"""
    # Phase 4: 使用 DAO 层
    character_dao = CharacterDAO(db)
    character = character_dao.update(character_id, data)
    if not character:
        return None
    return _character_to_response(character)


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
) -> Dict[str, Any]:
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
    return _alias_to_dict(alias_obj)


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
) -> Dict[str, Any]:
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
        return _attribute_to_dict(existing)
    
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
    return _attribute_to_dict(attr)


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
) -> Dict[str, Any]:
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
    return _relation_to_dict(relation)


def get_character_relations_impl(
    db: Session,
    character_id: int,
    relation_type: Optional[str] = None
) -> List[Dict[str, Any]]:
    """获取人物的所有关系"""
    query = db.query(CharacterRelation).filter(
        (CharacterRelation.source_character_id == character_id) |
        (CharacterRelation.target_character_id == character_id)
    )
    
    if relation_type:
        query = query.filter(CharacterRelation.relation_type == relation_type)
    
    relations = query.all()
    return [_relation_to_dict(r) for r in relations]


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
        "character": _character_to_response(character),
        "aliases": [_alias_to_dict(a) for a in character.aliases],
        "attributes": [_attribute_to_dict(a) for a in character.attributes],
        "arcs": [],  # TODO: 实现人物弧线
        "relations": [],  # TODO: 实现关系查询
    }
    
    return profile
