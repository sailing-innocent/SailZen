# -*- coding: utf-8 -*-
# @file character.py
# @brief Character Management Business Logic
# @author sailing-innocent
# @date 2025-02-01
# ---------------------------------

from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func

from sail_server.data.analysis import (
    Character, CharacterAlias, CharacterAttribute, CharacterArc, CharacterRelation,
    CharacterData, CharacterAliasData, CharacterAttributeData, CharacterArcData, CharacterRelationData,
    CharacterProfile, RelationGraphData,
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
    
    alias_count = db.query(func.count(CharacterAlias.id)).filter(
        CharacterAlias.character_id == character_id
    ).scalar() or 0
    
    attribute_count = db.query(func.count(CharacterAttribute.id)).filter(
        CharacterAttribute.character_id == character_id
    ).scalar() or 0
    
    relation_count = db.query(func.count(CharacterRelation.id)).filter(
        (CharacterRelation.source_character_id == character_id) |
        (CharacterRelation.target_character_id == character_id)
    ).scalar() or 0
    
    return CharacterData.read_from_orm(character, alias_count, attribute_count, relation_count)


def get_characters_by_edition_impl(
    db: Session, 
    edition_id: int, 
    role_type: Optional[str] = None,
    skip: int = 0, 
    limit: int = 100
) -> List[CharacterData]:
    """获取版本的所有人物"""
    query = db.query(Character).filter(Character.edition_id == edition_id)
    
    if role_type:
        query = query.filter(Character.role_type == role_type)
    
    characters = query.order_by(Character.importance_score.desc().nullslast(), Character.canonical_name).offset(skip).limit(limit).all()
    
    result = []
    for char in characters:
        alias_count = db.query(func.count(CharacterAlias.id)).filter(
            CharacterAlias.character_id == char.id
        ).scalar() or 0
        
        attribute_count = db.query(func.count(CharacterAttribute.id)).filter(
            CharacterAttribute.character_id == char.id
        ).scalar() or 0
        
        relation_count = db.query(func.count(CharacterRelation.id)).filter(
            (CharacterRelation.source_character_id == char.id) |
            (CharacterRelation.target_character_id == char.id)
        ).scalar() or 0
        
        result.append(CharacterData.read_from_orm(char, alias_count, attribute_count, relation_count))
    
    return result


def update_character_impl(db: Session, character_id: int, data: CharacterData) -> Optional[CharacterData]:
    """更新人物"""
    character = db.query(Character).filter(Character.id == character_id).first()
    if not character:
        return None
    
    data.update_orm(character)
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


def search_characters_impl(
    db: Session, 
    edition_id: int, 
    keyword: str, 
    skip: int = 0, 
    limit: int = 50
) -> List[CharacterData]:
    """搜索人物（包括别名）"""
    # 通过人物名搜索
    char_ids_by_name = db.query(Character.id).filter(
        Character.edition_id == edition_id,
        Character.canonical_name.ilike(f"%{keyword}%")
    ).all()
    
    # 通过别名搜索
    char_ids_by_alias = db.query(CharacterAlias.character_id).join(Character).filter(
        Character.edition_id == edition_id,
        CharacterAlias.alias.ilike(f"%{keyword}%")
    ).all()
    
    # 合并去重
    char_ids = list(set([c[0] for c in char_ids_by_name] + [c[0] for c in char_ids_by_alias]))
    
    if not char_ids:
        return []
    
    characters = db.query(Character).filter(
        Character.id.in_(char_ids)
    ).order_by(Character.importance_score.desc().nullslast()).offset(skip).limit(limit).all()
    
    return [CharacterData.read_from_orm(char) for char in characters]


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
) -> Optional[CharacterAliasData]:
    """添加人物别名"""
    character = db.query(Character).filter(Character.id == character_id).first()
    if not character:
        return None
    
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


def get_character_aliases_impl(db: Session, character_id: int) -> List[CharacterAliasData]:
    """获取人物的所有别名"""
    aliases = db.query(CharacterAlias).filter(
        CharacterAlias.character_id == character_id
    ).order_by(CharacterAlias.is_preferred.desc()).all()
    
    return [CharacterAliasData.read_from_orm(a) for a in aliases]


def remove_character_alias_impl(db: Session, alias_id: int) -> bool:
    """删除人物别名"""
    alias = db.query(CharacterAlias).filter(CharacterAlias.id == alias_id).first()
    if not alias:
        return False
    
    db.delete(alias)
    db.commit()
    return True


def get_character_by_alias_impl(db: Session, edition_id: int, alias: str) -> Optional[CharacterData]:
    """通过别名查找人物"""
    # 先精确匹配
    alias_obj = db.query(CharacterAlias).join(Character).filter(
        Character.edition_id == edition_id,
        CharacterAlias.alias == alias
    ).first()
    
    if alias_obj:
        character = db.query(Character).filter(Character.id == alias_obj.character_id).first()
        if character:
            return CharacterData.read_from_orm(character)
    
    # 再匹配canonical_name
    character = db.query(Character).filter(
        Character.edition_id == edition_id,
        Character.canonical_name == alias
    ).first()
    
    if character:
        return CharacterData.read_from_orm(character)
    
    return None


# ============================================================================
# Character Attribute Operations
# ============================================================================

def add_character_attribute_impl(
    db: Session,
    character_id: int,
    category: str,
    attr_key: str,
    attr_value: Any,
    confidence: Optional[float] = None,
    source_node_id: Optional[int] = None,
    source: str = "manual"
) -> Optional[CharacterAttributeData]:
    """添加人物属性"""
    character = db.query(Character).filter(Character.id == character_id).first()
    if not character:
        return None
    
    # 检查是否已存在
    existing = db.query(CharacterAttribute).filter(
        CharacterAttribute.character_id == character_id,
        CharacterAttribute.category == category,
        CharacterAttribute.attr_key == attr_key
    ).first()
    
    if existing:
        # 更新现有属性
        existing.attr_value = attr_value
        existing.confidence = confidence
        existing.source_node_id = source_node_id
        existing.source = source
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
        source=source,
    )
    db.add(attr)
    db.commit()
    db.refresh(attr)
    
    return CharacterAttributeData.read_from_orm(attr)


def get_character_attributes_impl(
    db: Session, 
    character_id: int, 
    category: Optional[str] = None
) -> List[CharacterAttributeData]:
    """获取人物属性"""
    query = db.query(CharacterAttribute).filter(
        CharacterAttribute.character_id == character_id
    )
    
    if category:
        query = query.filter(CharacterAttribute.category == category)
    
    attrs = query.order_by(CharacterAttribute.category, CharacterAttribute.attr_key).all()
    
    return [CharacterAttributeData.read_from_orm(a) for a in attrs]


def update_character_attribute_impl(
    db: Session, 
    attr_id: int, 
    attr_value: Any,
    status: Optional[str] = None
) -> Optional[CharacterAttributeData]:
    """更新人物属性"""
    attr = db.query(CharacterAttribute).filter(CharacterAttribute.id == attr_id).first()
    if not attr:
        return None
    
    attr.attr_value = attr_value
    if status:
        attr.status = status
    
    db.commit()
    db.refresh(attr)
    return CharacterAttributeData.read_from_orm(attr)


def delete_character_attribute_impl(db: Session, attr_id: int) -> bool:
    """删除人物属性"""
    attr = db.query(CharacterAttribute).filter(CharacterAttribute.id == attr_id).first()
    if not attr:
        return False
    
    db.delete(attr)
    db.commit()
    return True


# ============================================================================
# Character Arc Operations
# ============================================================================

def add_character_arc_impl(
    db: Session,
    character_id: int,
    arc_type: str,
    title: str,
    description: Optional[str] = None,
    start_node_id: Optional[int] = None,
    end_node_id: Optional[int] = None
) -> Optional[CharacterArcData]:
    """添加人物弧线"""
    character = db.query(Character).filter(Character.id == character_id).first()
    if not character:
        return None
    
    arc = CharacterArc(
        character_id=character_id,
        arc_type=arc_type,
        title=title,
        description=description,
        start_node_id=start_node_id,
        end_node_id=end_node_id,
    )
    db.add(arc)
    db.commit()
    db.refresh(arc)
    
    return CharacterArcData.read_from_orm(arc)


def get_character_arcs_impl(db: Session, character_id: int) -> List[CharacterArcData]:
    """获取人物弧线"""
    arcs = db.query(CharacterArc).filter(
        CharacterArc.character_id == character_id
    ).order_by(CharacterArc.created_at).all()
    
    return [CharacterArcData.read_from_orm(a) for a in arcs]


def delete_character_arc_impl(db: Session, arc_id: int) -> bool:
    """删除人物弧线"""
    arc = db.query(CharacterArc).filter(CharacterArc.id == arc_id).first()
    if not arc:
        return False
    
    db.delete(arc)
    db.commit()
    return True


# ============================================================================
# Character Relation Operations
# ============================================================================

def create_character_relation_impl(db: Session, data: CharacterRelationData) -> CharacterRelationData:
    """创建人物关系"""
    relation = data.create_orm()
    db.add(relation)
    db.commit()
    db.refresh(relation)
    
    # 获取人物名称
    source_char = db.query(Character).filter(Character.id == relation.source_character_id).first()
    target_char = db.query(Character).filter(Character.id == relation.target_character_id).first()
    
    return CharacterRelationData.read_from_orm(
        relation,
        source_name=source_char.canonical_name if source_char else None,
        target_name=target_char.canonical_name if target_char else None,
    )


def get_character_relations_impl(db: Session, character_id: int) -> List[CharacterRelationData]:
    """获取人物的所有关系"""
    relations = db.query(CharacterRelation).filter(
        (CharacterRelation.source_character_id == character_id) |
        (CharacterRelation.target_character_id == character_id)
    ).all()
    
    result = []
    for rel in relations:
        source_char = db.query(Character).filter(Character.id == rel.source_character_id).first()
        target_char = db.query(Character).filter(Character.id == rel.target_character_id).first()
        result.append(CharacterRelationData.read_from_orm(
            rel,
            source_name=source_char.canonical_name if source_char else None,
            target_name=target_char.canonical_name if target_char else None,
        ))
    
    return result


def get_edition_relations_impl(db: Session, edition_id: int) -> List[CharacterRelationData]:
    """获取版本的所有人物关系"""
    relations = db.query(CharacterRelation).filter(
        CharacterRelation.edition_id == edition_id
    ).all()
    
    result = []
    for rel in relations:
        source_char = db.query(Character).filter(Character.id == rel.source_character_id).first()
        target_char = db.query(Character).filter(Character.id == rel.target_character_id).first()
        result.append(CharacterRelationData.read_from_orm(
            rel,
            source_name=source_char.canonical_name if source_char else None,
            target_name=target_char.canonical_name if target_char else None,
        ))
    
    return result


def update_character_relation_impl(
    db: Session, 
    relation_id: int, 
    data: CharacterRelationData
) -> Optional[CharacterRelationData]:
    """更新人物关系"""
    relation = db.query(CharacterRelation).filter(CharacterRelation.id == relation_id).first()
    if not relation:
        return None
    
    data.update_orm(relation)
    db.commit()
    db.refresh(relation)
    
    source_char = db.query(Character).filter(Character.id == relation.source_character_id).first()
    target_char = db.query(Character).filter(Character.id == relation.target_character_id).first()
    
    return CharacterRelationData.read_from_orm(
        relation,
        source_name=source_char.canonical_name if source_char else None,
        target_name=target_char.canonical_name if target_char else None,
    )


def delete_character_relation_impl(db: Session, relation_id: int) -> bool:
    """删除人物关系"""
    relation = db.query(CharacterRelation).filter(CharacterRelation.id == relation_id).first()
    if not relation:
        return False
    
    db.delete(relation)
    db.commit()
    return True


# ============================================================================
# Character Profile (Composite)
# ============================================================================

def get_character_profile_impl(db: Session, character_id: int) -> Optional[CharacterProfile]:
    """获取完整的人物档案"""
    character = db.query(Character).filter(Character.id == character_id).first()
    if not character:
        return None
    
    # 基本信息
    char_data = CharacterData.read_from_orm(character)
    
    # 别名
    aliases = [CharacterAliasData.read_from_orm(a) for a in character.aliases]
    
    # 属性（按分类分组）
    attributes_by_category: Dict[str, List[CharacterAttributeData]] = {}
    for attr in character.attributes:
        attr_data = CharacterAttributeData.read_from_orm(attr)
        if attr.category not in attributes_by_category:
            attributes_by_category[attr.category] = []
        attributes_by_category[attr.category].append(attr_data)
    
    # 弧线
    arcs = [CharacterArcData.read_from_orm(a) for a in character.arcs]
    
    # 关系
    relations = get_character_relations_impl(db, character_id)
    
    # 设定关联
    from sail_server.data.analysis import CharacterSettingLink, Setting, CharacterSettingLinkData
    setting_links_orm = db.query(CharacterSettingLink).filter(
        CharacterSettingLink.character_id == character_id
    ).all()
    setting_links = []
    for link in setting_links_orm:
        setting = db.query(Setting).filter(Setting.id == link.setting_id).first()
        setting_links.append(CharacterSettingLinkData.read_from_orm(
            link,
            character_name=character.canonical_name,
            setting_name=setting.canonical_name if setting else None,
        ))
    
    return CharacterProfile(
        character=char_data,
        aliases=aliases,
        attributes=attributes_by_category,
        arcs=arcs,
        relations=relations,
        setting_links=setting_links,
    )


# ============================================================================
# Relation Graph Data
# ============================================================================

def get_relation_graph_impl(db: Session, edition_id: int) -> RelationGraphData:
    """获取关系图数据（用于可视化）"""
    # 获取所有人物
    characters = db.query(Character).filter(Character.edition_id == edition_id).all()
    
    nodes = []
    for char in characters:
        nodes.append({
            "id": char.id,
            "name": char.canonical_name,
            "role_type": char.role_type,
            "importance_score": float(char.importance_score) if char.importance_score else 0.5,
        })
    
    # 获取所有关系
    relations = db.query(CharacterRelation).filter(
        CharacterRelation.edition_id == edition_id
    ).all()
    
    edges = []
    for rel in relations:
        edges.append({
            "source": rel.source_character_id,
            "target": rel.target_character_id,
            "relation_type": rel.relation_type,
            "relation_subtype": rel.relation_subtype,
            "strength": float(rel.strength) if rel.strength else 0.5,
            "is_mutual": rel.is_mutual,
        })
    
    return RelationGraphData(nodes=nodes, edges=edges)
