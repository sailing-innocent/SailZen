# -*- coding: utf-8 -*-
# @file setting.py
# @brief Setting ORM Models
# @author sailing-innocent
# @date 2026-03-01
# @version 1.0
# ---------------------------------

"""
设定相关 ORM 模型

从 sail_server/data/analysis.py 迁移至此
"""

from sqlalchemy import (
    Column, Integer, String, Text, TIMESTAMP, ForeignKey, func
)
from sqlalchemy.orm import relationship

from sail_server.data.types import JSONB
from sail_server.infrastructure.orm import ORMBase


class Setting(ORMBase):
    """设定 ORM 模型"""
    __tablename__ = "novel_settings"
    
    id = Column(Integer, primary_key=True)
    edition_id = Column(Integer, ForeignKey("editions.id", ondelete="CASCADE"), nullable=False)
    setting_type = Column(String, nullable=False)  # item, location, organization, concept, magic_system, creature, event_type
    canonical_name = Column(String, nullable=False)
    category = Column(String, nullable=True)  # 子分类
    description = Column(Text, nullable=True)
    first_appearance_node_id = Column(Integer, ForeignKey("document_nodes.id", ondelete="SET NULL"), nullable=True)
    importance = Column(String, nullable=True, default="normal")  # critical, major, normal, minor
    status = Column(String, nullable=True, default="draft")
    source = Column(String, nullable=True, default="manual")
    meta_data = Column(JSONB, default={})
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    
    # 关联
    attributes = relationship("SettingAttribute", back_populates="setting", cascade="all, delete-orphan")


class SettingAttribute(ORMBase):
    """设定属性 ORM 模型"""
    __tablename__ = "setting_attributes"
    
    id = Column(Integer, primary_key=True)
    setting_id = Column(Integer, ForeignKey("novel_settings.id", ondelete="CASCADE"), nullable=False)
    attr_key = Column(String, nullable=False)
    attr_value = Column(Text, nullable=False)
    source = Column(String, nullable=True, default="manual")
    source_node_id = Column(Integer, ForeignKey("document_nodes.id", ondelete="SET NULL"), nullable=True)
    status = Column(String, nullable=True, default="pending")
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    
    # 关联
    setting = relationship("Setting", back_populates="attributes")


class SettingRelation(ORMBase):
    """设定关系 ORM 模型"""
    __tablename__ = "setting_relations"
    
    id = Column(Integer, primary_key=True)
    edition_id = Column(Integer, ForeignKey("editions.id", ondelete="CASCADE"), nullable=False)
    source_setting_id = Column(Integer, ForeignKey("novel_settings.id", ondelete="CASCADE"), nullable=False)
    target_setting_id = Column(Integer, ForeignKey("novel_settings.id", ondelete="CASCADE"), nullable=False)
    relation_type = Column(String, nullable=False)  # contains, belongs_to, produces, requires, opposes
    description = Column(Text, nullable=True)
    meta_data = Column(JSONB, default={})
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())


class CharacterSettingLink(ORMBase):
    """人物-设定关联 ORM 模型"""
    __tablename__ = "character_setting_links"
    
    id = Column(Integer, primary_key=True)
    character_id = Column(Integer, ForeignKey("characters.id", ondelete="CASCADE"), nullable=False)
    setting_id = Column(Integer, ForeignKey("novel_settings.id", ondelete="CASCADE"), nullable=False)
    link_type = Column(String, nullable=False)  # owns, belongs_to, created, uses, guards
    description = Column(Text, nullable=True)
    start_node_id = Column(Integer, ForeignKey("document_nodes.id", ondelete="SET NULL"), nullable=True)
    end_node_id = Column(Integer, ForeignKey("document_nodes.id", ondelete="SET NULL"), nullable=True)
    meta_data = Column(JSONB, default={})
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
