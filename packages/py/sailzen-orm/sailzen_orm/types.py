# -*- coding: utf-8 -*-
# @file types.py
# @brief Database type compatibility layer
# @author sailing-innocent
# @date 2026-02-28
# @version 1.0
# ---------------------------------
#
# Database type compatibility layer for cross-database support.
# Provides PostgreSQL-specific types (JSONB, ARRAY) with fallback to
# generic types for SQLite and other databases.

from typing import Any, Dict, List, Optional, Type
import json

from sqlalchemy import TypeDecorator, Text, String
from sqlalchemy.dialects.postgresql import JSONB as PGJSONB
from sqlalchemy.dialects.postgresql import ARRAY as PGARRAY


class JSONB(TypeDecorator):
    """
    Cross-database JSONB type.

    Uses PostgreSQL's native JSONB when available,
    falls back to Text with JSON serialization for SQLite.
    """

    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PGJSONB())
        else:
            return dialect.type_descriptor(Text())

    def process_bind_param(
        self, value: Optional[Dict[str, Any]], dialect
    ) -> Optional[str]:
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value
        return json.dumps(value)

    def process_result_value(
        self, value: Optional[str], dialect
    ) -> Optional[Dict[str, Any]]:
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value
        if isinstance(value, str):
            return json.loads(value)
        return value


class ARRAY(TypeDecorator):
    """
    Cross-database ARRAY type.

    Uses PostgreSQL's native ARRAY when available,
    falls back to Text with JSON serialization for SQLite.
    """

    impl = Text
    cache_ok = True

    def __init__(self, item_type: Type = String, dimensions: int = 1, **kwargs):
        self.item_type = item_type
        self.dimensions = dimensions
        super().__init__(**kwargs)

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(
                PGARRAY(self.item_type, dimensions=self.dimensions)
            )
        else:
            return dialect.type_descriptor(Text())

    def process_bind_param(self, value: Optional[List[Any]], dialect) -> Optional[str]:
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value
        return json.dumps(value)

    def process_result_value(
        self, value: Optional[str], dialect
    ) -> Optional[List[Any]]:
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value
        if isinstance(value, str):
            return json.loads(value)
        return value
