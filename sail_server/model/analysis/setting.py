# -*- coding: utf-8 -*-
# @file setting.py
# @brief Setting Management Business Logic
# @author sailing-innocent
# @date 2025-02-01
# ---------------------------------

from typing import Optional, List, Any
from sqlalchemy.orm import Session
from sqlalchemy import func

from sail_server.data.analysis import (
    Setting, SettingAttribute, SettingRelation, CharacterSettingLink, Character,
    SettingData, SettingAttributeData, SettingRelationData, CharacterSettingLinkData,
    SettingDetail,
)


# ============================================================================
# Setting CRUD Operations
# ============================================================================

def create_setting_impl(db: Session, data: SettingData) -> SettingData:
    """创建设定"""
    setting = data.create_orm()
    db.add(setting)
    db.commit()
    db.refresh(setting)
    return SettingData.read_from_orm(setting)


def get_setting_impl(db: Session, setting_id: int) -> Optional[SettingData]:
    """获取单个设定"""
    setting = db.query(Setting).filter(Setting.id == setting_id).first()
    if not setting:
        return None
    
    attribute_count = db.query(func.count(SettingAttribute.id)).filter(
        SettingAttribute.setting_id == setting_id
    ).scalar() or 0
    
    character_link_count = db.query(func.count(CharacterSettingLink.id)).filter(
        CharacterSettingLink.setting_id == setting_id
    ).scalar() or 0
    
    return SettingData.read_from_orm(setting, attribute_count, character_link_count)


def get_settings_by_edition_impl(
    db: Session, 
    edition_id: int, 
    setting_type: Optional[str] = None,
    category: Optional[str] = None,
    skip: int = 0, 
    limit: int = 100
) -> List[SettingData]:
    """获取版本的设定列表"""
    query = db.query(Setting).filter(Setting.edition_id == edition_id)
    
    if setting_type:
        query = query.filter(Setting.setting_type == setting_type)
    
    if category:
        query = query.filter(Setting.category == category)
    
    settings = query.order_by(Setting.setting_type, Setting.canonical_name).offset(skip).limit(limit).all()
    
    result = []
    for s in settings:
        attribute_count = db.query(func.count(SettingAttribute.id)).filter(
            SettingAttribute.setting_id == s.id
        ).scalar() or 0
        
        character_link_count = db.query(func.count(CharacterSettingLink.id)).filter(
            CharacterSettingLink.setting_id == s.id
        ).scalar() or 0
        
        result.append(SettingData.read_from_orm(s, attribute_count, character_link_count))
    
    return result


def update_setting_impl(db: Session, setting_id: int, data: SettingData) -> Optional[SettingData]:
    """更新设定"""
    setting = db.query(Setting).filter(Setting.id == setting_id).first()
    if not setting:
        return None
    
    data.update_orm(setting)
    db.commit()
    db.refresh(setting)
    return SettingData.read_from_orm(setting)


def delete_setting_impl(db: Session, setting_id: int) -> bool:
    """删除设定"""
    setting = db.query(Setting).filter(Setting.id == setting_id).first()
    if not setting:
        return False
    
    db.delete(setting)
    db.commit()
    return True


def search_settings_impl(
    db: Session, 
    edition_id: int, 
    keyword: str, 
    setting_type: Optional[str] = None,
    skip: int = 0, 
    limit: int = 50
) -> List[SettingData]:
    """搜索设定"""
    query = db.query(Setting).filter(
        Setting.edition_id == edition_id,
        Setting.canonical_name.ilike(f"%{keyword}%")
    )
    
    if setting_type:
        query = query.filter(Setting.setting_type == setting_type)
    
    settings = query.order_by(Setting.canonical_name).offset(skip).limit(limit).all()
    
    return [SettingData.read_from_orm(s) for s in settings]


# ============================================================================
# Setting Attribute Operations
# ============================================================================

def add_setting_attribute_impl(
    db: Session,
    setting_id: int,
    attr_key: str,
    attr_value: Any,
    source_node_id: Optional[int] = None,
    source: str = "manual"
) -> Optional[SettingAttributeData]:
    """添加设定属性"""
    setting = db.query(Setting).filter(Setting.id == setting_id).first()
    if not setting:
        return None
    
    # 检查是否已存在
    existing = db.query(SettingAttribute).filter(
        SettingAttribute.setting_id == setting_id,
        SettingAttribute.attr_key == attr_key
    ).first()
    
    if existing:
        # 更新现有属性
        existing.attr_value = attr_value
        existing.source_node_id = source_node_id
        existing.source = source
        db.commit()
        db.refresh(existing)
        return SettingAttributeData.read_from_orm(existing)
    
    # 创建新属性
    attr = SettingAttribute(
        setting_id=setting_id,
        attr_key=attr_key,
        attr_value=attr_value,
        source_node_id=source_node_id,
        source=source,
    )
    db.add(attr)
    db.commit()
    db.refresh(attr)
    
    return SettingAttributeData.read_from_orm(attr)


def get_setting_attributes_impl(db: Session, setting_id: int) -> List[SettingAttributeData]:
    """获取设定属性"""
    attrs = db.query(SettingAttribute).filter(
        SettingAttribute.setting_id == setting_id
    ).order_by(SettingAttribute.attr_key).all()
    
    return [SettingAttributeData.read_from_orm(a) for a in attrs]


def delete_setting_attribute_impl(db: Session, attr_id: int) -> bool:
    """删除设定属性"""
    attr = db.query(SettingAttribute).filter(SettingAttribute.id == attr_id).first()
    if not attr:
        return False
    
    db.delete(attr)
    db.commit()
    return True


# ============================================================================
# Setting Relation Operations
# ============================================================================

def create_setting_relation_impl(db: Session, data: SettingRelationData) -> SettingRelationData:
    """创建设定关系"""
    relation = data.create_orm()
    db.add(relation)
    db.commit()
    db.refresh(relation)
    
    # 获取设定名称
    source_setting = db.query(Setting).filter(Setting.id == relation.source_setting_id).first()
    target_setting = db.query(Setting).filter(Setting.id == relation.target_setting_id).first()
    
    return SettingRelationData.read_from_orm(
        relation,
        source_name=source_setting.canonical_name if source_setting else None,
        target_name=target_setting.canonical_name if target_setting else None,
    )


def get_setting_relations_impl(db: Session, setting_id: int) -> List[SettingRelationData]:
    """获取设定的所有关系"""
    relations = db.query(SettingRelation).filter(
        (SettingRelation.source_setting_id == setting_id) |
        (SettingRelation.target_setting_id == setting_id)
    ).all()
    
    result = []
    for rel in relations:
        source_setting = db.query(Setting).filter(Setting.id == rel.source_setting_id).first()
        target_setting = db.query(Setting).filter(Setting.id == rel.target_setting_id).first()
        result.append(SettingRelationData.read_from_orm(
            rel,
            source_name=source_setting.canonical_name if source_setting else None,
            target_name=target_setting.canonical_name if target_setting else None,
        ))
    
    return result


def delete_setting_relation_impl(db: Session, relation_id: int) -> bool:
    """删除设定关系"""
    relation = db.query(SettingRelation).filter(SettingRelation.id == relation_id).first()
    if not relation:
        return False
    
    db.delete(relation)
    db.commit()
    return True


# ============================================================================
# Character-Setting Link Operations
# ============================================================================

def create_character_setting_link_impl(
    db: Session,
    character_id: int,
    setting_id: int,
    link_type: str,
    description: Optional[str] = None,
    start_node_id: Optional[int] = None,
    end_node_id: Optional[int] = None
) -> Optional[CharacterSettingLinkData]:
    """创建人物-设定关联"""
    # 验证人物和设定存在
    character = db.query(Character).filter(Character.id == character_id).first()
    setting = db.query(Setting).filter(Setting.id == setting_id).first()
    
    if not character or not setting:
        return None
    
    link = CharacterSettingLink(
        character_id=character_id,
        setting_id=setting_id,
        link_type=link_type,
        description=description,
        start_node_id=start_node_id,
        end_node_id=end_node_id,
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    
    return CharacterSettingLinkData.read_from_orm(
        link,
        character_name=character.canonical_name,
        setting_name=setting.canonical_name,
    )


def get_character_settings_impl(db: Session, character_id: int) -> List[SettingData]:
    """获取人物关联的设定"""
    links = db.query(CharacterSettingLink).filter(
        CharacterSettingLink.character_id == character_id
    ).all()
    
    result = []
    for link in links:
        setting = db.query(Setting).filter(Setting.id == link.setting_id).first()
        if setting:
            result.append(SettingData.read_from_orm(setting))
    
    return result


def get_setting_characters_impl(db: Session, setting_id: int) -> List[dict]:
    """获取设定关联的人物（包含关联类型）"""
    links = db.query(CharacterSettingLink).filter(
        CharacterSettingLink.setting_id == setting_id
    ).all()
    
    result = []
    for link in links:
        character = db.query(Character).filter(Character.id == link.character_id).first()
        if character:
            result.append({
                "character_id": character.id,
                "canonical_name": character.canonical_name,
                "role_type": character.role_type,
                "link_type": link.link_type,
                "description": link.description,
            })
    
    return result


def delete_character_setting_link_impl(db: Session, link_id: int) -> bool:
    """删除人物-设定关联"""
    link = db.query(CharacterSettingLink).filter(CharacterSettingLink.id == link_id).first()
    if not link:
        return False
    
    db.delete(link)
    db.commit()
    return True


# ============================================================================
# Setting Detail (Composite)
# ============================================================================

def get_setting_detail_impl(db: Session, setting_id: int) -> Optional[SettingDetail]:
    """获取设定详情"""
    setting = db.query(Setting).filter(Setting.id == setting_id).first()
    if not setting:
        return None
    
    # 基本信息
    setting_data = SettingData.read_from_orm(setting)
    
    # 属性
    attributes = [SettingAttributeData.read_from_orm(a) for a in setting.attributes]
    
    # 人物关联
    character_links_orm = db.query(CharacterSettingLink).filter(
        CharacterSettingLink.setting_id == setting_id
    ).all()
    character_links = []
    for link in character_links_orm:
        character = db.query(Character).filter(Character.id == link.character_id).first()
        character_links.append(CharacterSettingLinkData.read_from_orm(
            link,
            character_name=character.canonical_name if character else None,
            setting_name=setting.canonical_name,
        ))
    
    # 相关设定
    related_settings = get_setting_relations_impl(db, setting_id)
    
    return SettingDetail(
        setting=setting_data,
        attributes=attributes,
        character_links=character_links,
        related_settings=related_settings,
    )


# ============================================================================
# Utility Functions
# ============================================================================

def get_setting_types_impl(db: Session, edition_id: int) -> List[dict]:
    """获取版本中使用的设定类型统计"""
    result = db.query(
        Setting.setting_type,
        func.count(Setting.id).label('count')
    ).filter(
        Setting.edition_id == edition_id
    ).group_by(Setting.setting_type).all()
    
    return [{"type": r[0], "count": r[1]} for r in result]


def get_setting_categories_impl(db: Session, edition_id: int, setting_type: str) -> List[dict]:
    """获取某类型设定下的分类统计"""
    result = db.query(
        Setting.category,
        func.count(Setting.id).label('count')
    ).filter(
        Setting.edition_id == edition_id,
        Setting.setting_type == setting_type
    ).group_by(Setting.category).all()
    
    return [{"category": r[0] or "未分类", "count": r[1]} for r in result]
