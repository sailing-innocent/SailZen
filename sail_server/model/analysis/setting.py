# -*- coding: utf-8 -*-
# @file setting.py
# @brief Setting Management Business Logic
# @author sailing-innocent
# @date 2025-03-01
# @version 1.0
# ---------------------------------

from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func

from sail_server.data.analysis import (
    Setting, SettingData,
    SettingAttribute, SettingAttributeData,
    SettingRelation, SettingRelationData,
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
    return SettingData.read_from_orm(setting)


def get_settings_by_edition_impl(
    db: Session, 
    edition_id: int,
    setting_type: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None
) -> List[SettingData]:
    """获取版本的所有设定"""
    query = db.query(Setting).filter(Setting.edition_id == edition_id)
    
    if setting_type:
        query = query.filter(Setting.setting_type == setting_type)
    if category:
        query = query.filter(Setting.category == category)
    if status:
        query = query.filter(Setting.status == status)
    
    settings = query.order_by(Setting.importance.desc(), Setting.canonical_name).all()
    return [SettingData.read_from_orm(s) for s in settings]


def update_setting_impl(
    db: Session, 
    setting_id: int, 
    data: Dict[str, Any]
) -> Optional[SettingData]:
    """更新设定"""
    setting = db.query(Setting).filter(Setting.id == setting_id).first()
    if not setting:
        return None
    
    # 更新字段
    for key, value in data.items():
        if hasattr(setting, key) and value is not None:
            setattr(setting, key, value)
    
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


# ============================================================================
# Setting Attribute Operations
# ============================================================================

def add_setting_attribute_impl(
    db: Session,
    setting_id: int,
    attr_key: str,
    attr_value: str,
    source_node_id: Optional[int] = None,
) -> SettingAttributeData:
    """添加设定属性"""
    # 检查是否已存在相同 key 的属性
    existing = db.query(SettingAttribute).filter(
        SettingAttribute.setting_id == setting_id,
        SettingAttribute.attr_key == attr_key
    ).first()
    
    if existing:
        # 更新现有属性
        existing.attr_value = attr_value
        existing.source_node_id = source_node_id
        db.commit()
        db.refresh(existing)
        return SettingAttributeData.read_from_orm(existing)
    
    # 创建新属性
    attr = SettingAttribute(
        setting_id=setting_id,
        attr_key=attr_key,
        attr_value=attr_value,
        source_node_id=source_node_id,
    )
    db.add(attr)
    db.commit()
    db.refresh(attr)
    return SettingAttributeData.read_from_orm(attr)


def delete_setting_attribute_impl(db: Session, attribute_id: int) -> bool:
    """删除设定属性"""
    attr = db.query(SettingAttribute).filter(SettingAttribute.id == attribute_id).first()
    if not attr:
        return False
    
    db.delete(attr)
    db.commit()
    return True


# ============================================================================
# Setting Relation Operations
# ============================================================================

def add_setting_relation_impl(
    db: Session,
    edition_id: int,
    source_setting_id: int,
    target_setting_id: int,
    relation_type: str,
    description: Optional[str] = None,
) -> SettingRelationData:
    """添加设定关系"""
    relation = SettingRelation(
        edition_id=edition_id,
        source_setting_id=source_setting_id,
        target_setting_id=target_setting_id,
        relation_type=relation_type,
        description=description,
    )
    db.add(relation)
    db.commit()
    db.refresh(relation)
    return SettingRelationData.read_from_orm(relation)


def get_setting_relations_impl(
    db: Session,
    setting_id: int,
    relation_type: Optional[str] = None
) -> List[SettingRelationData]:
    """获取设定的所有关系"""
    query = db.query(SettingRelation).filter(
        (SettingRelation.source_setting_id == setting_id) |
        (SettingRelation.target_setting_id == setting_id)
    )
    
    if relation_type:
        query = query.filter(SettingRelation.relation_type == relation_type)
    
    relations = query.all()
    return [SettingRelationData.read_from_orm(r) for r in relations]


def delete_setting_relation_impl(db: Session, relation_id: int) -> bool:
    """删除设定关系"""
    relation = db.query(SettingRelation).filter(SettingRelation.id == relation_id).first()
    if not relation:
        return False
    
    db.delete(relation)
    db.commit()
    return True


# ============================================================================
# Setting Type Operations
# ============================================================================

SETTING_TYPES = [
    ("item", "物品"),
    ("location", "地点"),
    ("organization", "组织"),
    ("concept", "概念"),
    ("magic_system", "力量体系"),
    ("creature", "生物"),
    ("event_type", "事件类型"),
]

SETTING_TYPE_LABELS = {
    "item": "物品",
    "location": "地点",
    "organization": "组织",
    "concept": "概念",
    "magic_system": "力量体系",
    "creature": "生物",
    "event_type": "事件类型",
}


def get_setting_types_impl() -> Dict[str, Any]:
    """获取设定类型列表"""
    return {
        "types": [t[0] for t in SETTING_TYPES],
        "labels": SETTING_TYPE_LABELS,
    }
