# -*- coding: utf-8 -*-
# @file character.py
# @brief Character ORM Models
# @author sailing-innocent
# @date 2026-03-01
# @version 1.0
# ---------------------------------

"""
人物相关 ORM 模型

从 sail_server/data/analysis.py 迁移至此
"""

from sqlalchemy import (
    Column, Integer, String, Text, TIMESTAMP, ForeignKey, func, Float, Boolean
)
from sqlalchemy.orm import relationship

from sail_server.data.types import JSONB
from sail_server.infrastructure.orm import ORMBase


class Character(ORMBase):
    """人物 ORM 模型"""
    __tablename__ = "characters"
    
    id = Column(Integer, primary_key=True)
    edition_id = Column(Integer, ForeignKey("editions.id", ondelete="CASCADE"), nullable=False)
    canonical_name = Column(String, nullable=False)
    role_type = Column(String, nullable=True, default="supporting")  # protagonist, antagonist, deuteragonist, supporting, minor
    description = Column(Text, nullable=True)
    first_appearance_node_id = Column(Integer, ForeignKey("document_nodes.id", ondelete="SET NULL"), nullable=True)
    status = Column(String, nullable=True, default="draft")
    source = Column(String, nullable=True, default="manual")
    importance_score = Column(Float, nullable=True)
    meta_data = Column(JSONB, default={})
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    
    # 关联
    aliases = relationship("CharacterAlias", back_populates="character", cascade="all, delete-orphan")
    attributes = relationship("CharacterAttribute", back_populates="character", cascade="all, delete-orphan")
    arcs = relationship("CharacterArc", back_populates="character", cascade="all, delete-orphan")


class CharacterAlias(ORMBase):
    """人物别名 ORM 模型"""
    __tablename__ = "character_aliases"
    
    id = Column(Integer, primary_key=True)
    character_id = Column(Integer, ForeignKey("characters.id", ondelete="CASCADE"), nullable=False)
    alias = Column(String, nullable=False)
    alias_type = Column(String, nullable=True, default="nickname")  # nickname, title, formal, diminutive
    usage_context = Column(String, nullable=True)
    is_preferred = Column(Boolean, nullable=True, default=False)
    source = Column(String, nullable=True, default="manual")
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    
    # 关联
    character = relationship("Character", back_populates="aliases")


class CharacterAttribute(ORMBase):
    """人物属性 ORM 模型"""
    __tablename__ = "character_attributes"
    
    id = Column(Integer, primary_key=True)
    character_id = Column(Integer, ForeignKey("characters.id", ondelete="CASCADE"), nullable=False)
    category = Column(String, nullable=True)  # physical, personality, background, ability, etc.
    attr_key = Column(String, nullable=False)
    attr_value = Column(Text, nullable=False)
    confidence = Column(Float, nullable=True)
    source = Column(String, nullable=True, default="manual")
    source_node_id = Column(Integer, ForeignKey("document_nodes.id", ondelete="SET NULL"), nullable=True)
    status = Column(String, nullable=True, default="pending")
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    
    # 关联
    character = relationship("Character", back_populates="attributes")


class CharacterArc(ORMBase):
    """人物弧光 ORM 模型"""
    __tablename__ = "character_arcs"
    
    id = Column(Integer, primary_key=True)
    character_id = Column(Integer, ForeignKey("characters.id", ondelete="CASCADE"), nullable=False)
    arc_type = Column(String, nullable=True)  # growth, fall, redemption, tragic, etc.
    title = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    start_node_id = Column(Integer, ForeignKey("document_nodes.id", ondelete="SET NULL"), nullable=True)
    end_node_id = Column(Integer, ForeignKey("document_nodes.id", ondelete="SET NULL"), nullable=True)
    status = Column(String, nullable=True, default="draft")
    meta_data = Column(JSONB, default={})
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    
    # 关联
    character = relationship("Character", back_populates="arcs")


class CharacterRelation(ORMBase):
    """人物关系 ORM 模型"""
    __tablename__ = "character_relations"
    
    id = Column(Integer, primary_key=True)
    edition_id = Column(Integer, ForeignKey("editions.id", ondelete="CASCADE"), nullable=False)
    source_character_id = Column(Integer, ForeignKey("characters.id", ondelete="CASCADE"), nullable=False)
    target_character_id = Column(Integer, ForeignKey("characters.id", ondelete="CASCADE"), nullable=False)
    relation_type = Column(String, nullable=False)  # family, friend, enemy, romantic, professional, etc.
    relation_subtype = Column(String, nullable=True)  # parent, sibling, spouse, etc.
    description = Column(Text, nullable=True)
    strength = Column(Float, nullable=True)  # 关系强度 0-1
    is_mutual = Column(Boolean, nullable=True, default=True)
    start_node_id = Column(Integer, ForeignKey("document_nodes.id", ondelete="SET NULL"), nullable=True)
    end_node_id = Column(Integer, ForeignKey("document_nodes.id", ondelete="SET NULL"), nullable=True)
    status = Column(String, nullable=True, default="draft")
    meta_data = Column(JSONB, default={})
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
