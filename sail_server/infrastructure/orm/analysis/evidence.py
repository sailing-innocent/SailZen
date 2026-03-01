# -*- coding: utf-8 -*-
# @file evidence.py
# @brief Evidence ORM Models
# @author sailing-innocent
# @date 2026-03-01
# @version 1.0
# ---------------------------------

"""
证据相关 ORM 模型

从 sail_server/data/analysis.py 迁移至此
"""

from sqlalchemy import (
    Column, Integer, String, Text, TIMESTAMP, ForeignKey, func, Float
)

from sail_server.data.types import JSONB
from sail_server.infrastructure.orm import ORMBase


class TextEvidence(ORMBase):
    """文本证据 ORM 模型"""
    __tablename__ = "text_evidence"
    
    id = Column(Integer, primary_key=True)
    edition_id = Column(Integer, ForeignKey("editions.id", ondelete="CASCADE"), nullable=False)
    node_id = Column(Integer, ForeignKey("document_nodes.id", ondelete="CASCADE"), nullable=False)
    target_type = Column(String, nullable=False)  # outline_node | character | setting | etc.
    target_id = Column(Integer, nullable=False)
    start_char = Column(Integer, nullable=True)
    end_char = Column(Integer, nullable=True)
    text_snippet = Column(Text, nullable=True)
    context_before = Column(Text, nullable=True)
    context_after = Column(Text, nullable=True)
    evidence_type = Column(String, nullable=True, default="explicit")
    confidence = Column(Float, nullable=True)
    source = Column(String, nullable=True, default="manual")
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
