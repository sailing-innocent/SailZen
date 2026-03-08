# -*- coding: utf-8 -*-
# @file pagination.py
# @brief Cursor-based pagination utilities for large datasets
# @author sailing-innocent
# @date 2026-03-07
# @version 1.0
# ---------------------------------

import base64
import json
from dataclasses import dataclass
from typing import Any, Dict, Generic, List, Optional, TypeVar

T = TypeVar('T')


@dataclass
class PaginationCursor:
    """Cursor for pagination containing position information."""
    sort_index: int
    node_id: int
    
    def encode(self) -> str:
        """Encode cursor to base64 string."""
        data = json.dumps({
            'si': self.sort_index,
            'ni': self.node_id
        })
        return base64.urlsafe_b64encode(data.encode()).decode().rstrip('=')
    
    @classmethod
    def decode(cls, cursor_str: str) -> 'PaginationCursor':
        """Decode cursor from base64 string."""
        # Add padding if needed
        padding = 4 - len(cursor_str) % 4
        if padding != 4:
            cursor_str += '=' * padding
        
        data = json.loads(base64.urlsafe_b64decode(cursor_str.encode()).decode())
        return cls(
            sort_index=data['si'],
            node_id=data['ni']
        )


@dataclass
class PaginatedResponse(Generic[T]):
    """Generic paginated response structure."""
    items: List[T]
    next_cursor: Optional[str]
    has_more: bool
    total_count: Optional[int] = None


def create_paginated_response(
    items: List[T],
    limit: int,
    cursor_factory: Optional[Any] = None
) -> PaginatedResponse[T]:
    """Create paginated response from items list.
    
    Args:
        items: List of items (may contain limit+1 items to check for more)
        limit: Requested page size
        cursor_factory: Function to create cursor from last item
        
    Returns:
        PaginatedResponse with items and pagination metadata
    """
    has_more = len(items) > limit
    items_to_return = items[:limit] if has_more else items
    
    next_cursor = None
    if has_more and items_to_return and cursor_factory:
        last_item = items_to_return[-1]
        next_cursor = cursor_factory(last_item)
    
    return PaginatedResponse(
        items=items_to_return,
        next_cursor=next_cursor,
        has_more=has_more
    )


def parse_pagination_params(
    cursor_str: Optional[str] = None,
    limit: int = 50,
    max_limit: int = 100
) -> tuple[Optional[PaginationCursor], int]:
    """Parse and validate pagination parameters.
    
    Args:
        cursor_str: Encoded cursor string
        limit: Requested page size
        max_limit: Maximum allowed page size
        
    Returns:
        Tuple of (cursor, validated_limit)
    """
    cursor = None
    if cursor_str:
        try:
            cursor = PaginationCursor.decode(cursor_str)
        except (ValueError, json.JSONDecodeError, KeyError):
            raise ValueError("Invalid cursor format")
    
    # Validate and clamp limit
    limit = max(1, min(limit, max_limit))
    
    return cursor, limit


def apply_cursor_filter(query, cursor: PaginationCursor, sort_column='sort_index', id_column='id'):
    """Apply cursor-based filtering to SQLAlchemy query.
    
    Args:
        query: SQLAlchemy query object
        cursor: PaginationCursor with position info
        sort_column: Name of the sort column (default: sort_index)
        id_column: Name of the ID column (default: id)
        
    Returns:
        Modified query with cursor filter applied
    """
    from sqlalchemy import or_, and_
    
    sort_attr = getattr(query.column_descriptions[0]['type'], sort_column)
    id_attr = getattr(query.column_descriptions[0]['type'], id_column)
    
    # Cursor logic: (sort_index > cursor.sort_index) OR 
    #               (sort_index == cursor.sort_index AND id > cursor.node_id)
    query = query.filter(
        or_(
            sort_attr > cursor.sort_index,
            and_(
                sort_attr == cursor.sort_index,
                id_attr > cursor.node_id
            )
        )
    )
    
    return query
