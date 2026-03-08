# -*- coding: utf-8 -*-
# @file test_utils_pagination.py
# @brief pagination utility unit tests
# @author sailing-innocent
# @date 2026-03-08
# @version 1.0
# ---------------------------------

"""
Cursor-based pagination utility unit tests

Test coverage:
- PaginationCursor encoding/decoding
- PaginatedResponse creation
- Pagination parameter parsing
- Cursor filter application
- Edge cases and error handling
"""

import pytest
from dataclasses import dataclass
from typing import List

from sail_server.utils.pagination import (
    PaginationCursor,
    PaginatedResponse,
    create_paginated_response,
    parse_pagination_params,
)


@dataclass
class MockItem:
    """Mock item for testing pagination"""
    id: int
    sort_index: int
    name: str


class TestPaginationCursor:
    """Test PaginationCursor encoding and decoding"""
    
    def test_cursor_encode_basic(self):
        """Test basic cursor encoding"""
        cursor = PaginationCursor(sort_index=10, node_id=123)
        encoded = cursor.encode()
        assert isinstance(encoded, str)
        assert len(encoded) > 0
    
    def test_cursor_decode_basic(self):
        """Test basic cursor decoding"""
        cursor = PaginationCursor(sort_index=10, node_id=123)
        encoded = cursor.encode()
        decoded = PaginationCursor.decode(encoded)
        assert decoded.sort_index == 10
        assert decoded.node_id == 123
    
    def test_cursor_encode_decode_zero_values(self):
        """Test cursor with zero values"""
        cursor = PaginationCursor(sort_index=0, node_id=0)
        encoded = cursor.encode()
        decoded = PaginationCursor.decode(encoded)
        assert decoded.sort_index == 0
        assert decoded.node_id == 0
    
    def test_cursor_encode_decode_large_values(self):
        """Test cursor with large values"""
        cursor = PaginationCursor(sort_index=999999, node_id=999999999)
        encoded = cursor.encode()
        decoded = PaginationCursor.decode(encoded)
        assert decoded.sort_index == 999999
        assert decoded.node_id == 999999999
    
    def test_cursor_encode_decode_negative_values(self):
        """Test cursor with negative values"""
        cursor = PaginationCursor(sort_index=-5, node_id=-100)
        encoded = cursor.encode()
        decoded = PaginationCursor.decode(encoded)
        assert decoded.sort_index == -5
        assert decoded.node_id == -100
    
    def test_cursor_url_safe_encoding(self):
        """Test that encoding produces URL-safe strings"""
        cursor = PaginationCursor(sort_index=100, node_id=200)
        encoded = cursor.encode()
        # URL-safe base64 should not contain + or /
        assert '+' not in encoded
        assert '/' not in encoded
        # Should not contain padding
        assert '=' not in encoded
    
    def test_cursor_padding_handling(self):
        """Test proper handling of base64 padding"""
        # Create cursor that might produce different padding lengths
        for sort_idx in range(10):
            for node_idx in range(10):
                cursor = PaginationCursor(sort_index=sort_idx, node_id=node_idx)
                encoded = cursor.encode()
                decoded = PaginationCursor.decode(encoded)
                assert decoded.sort_index == sort_idx
                assert decoded.node_id == node_idx
    
    def test_cursor_decode_invalid_base64(self):
        """Test decoding invalid base64 string"""
        with pytest.raises(Exception):  # Could be ValueError or binascii.Error
            PaginationCursor.decode("!!!invalid!!!")
    
    def test_cursor_decode_invalid_json(self):
        """Test decoding valid base64 but invalid JSON"""
        import base64
        invalid_json = base64.urlsafe_b64encode(b"not json").decode().rstrip('=')
        with pytest.raises((ValueError, KeyError)):
            PaginationCursor.decode(invalid_json)
    
    def test_cursor_decode_missing_keys(self):
        """Test decoding JSON with missing keys"""
        import base64
        import json
        data = json.dumps({"si": 10})  # Missing 'ni' key
        encoded = base64.urlsafe_b64encode(data.encode()).decode().rstrip('=')
        with pytest.raises(KeyError):
            PaginationCursor.decode(encoded)


class TestCreatePaginatedResponse:
    """Test create_paginated_response function"""
    
    def create_mock_items(self, count: int) -> List[MockItem]:
        """Helper to create mock items"""
        return [
            MockItem(id=i, sort_index=i * 10, name=f"Item {i}")
            for i in range(count)
        ]
    
    def test_paginated_response_no_cursor_factory(self):
        """Test response without cursor factory"""
        items = self.create_mock_items(10)
        response = create_paginated_response(items, limit=10, cursor_factory=None)
        
        assert len(response.items) == 10
        assert response.next_cursor is None
        assert response.has_more is False
    
    def test_paginated_response_exact_limit(self):
        """Test when items exactly match limit"""
        items = self.create_mock_items(10)
        
        def cursor_factory(item):
            return PaginationCursor(sort_index=item.sort_index, node_id=item.id).encode()
        
        response = create_paginated_response(items, limit=10, cursor_factory=cursor_factory)
        
        assert len(response.items) == 10
        assert response.has_more is False
        assert response.next_cursor is None
    
    def test_paginated_response_has_more(self):
        """Test when there are more items than limit"""
        items = self.create_mock_items(15)  # 15 items
        
        def cursor_factory(item):
            return PaginationCursor(sort_index=item.sort_index, node_id=item.id).encode()
        
        response = create_paginated_response(items, limit=10, cursor_factory=cursor_factory)
        
        assert len(response.items) == 10
        assert response.has_more is True
        assert response.next_cursor is not None
        # Last item should be item 9 (10th item, 0-indexed)
        last_item = response.items[-1]
        assert last_item.id == 9
    
    def test_paginated_response_empty_list(self):
        """Test with empty items list"""
        items = []
        
        def cursor_factory(item):
            return PaginationCursor(sort_index=item.sort_index, node_id=item.id).encode()
        
        response = create_paginated_response(items, limit=10, cursor_factory=cursor_factory)
        
        assert len(response.items) == 0
        assert response.has_more is False
        assert response.next_cursor is None
    
    def test_paginated_response_single_item(self):
        """Test with single item"""
        items = self.create_mock_items(1)
        
        def cursor_factory(item):
            return PaginationCursor(sort_index=item.sort_index, node_id=item.id).encode()
        
        response = create_paginated_response(items, limit=10, cursor_factory=cursor_factory)
        
        assert len(response.items) == 1
        assert response.has_more is False
        assert response.next_cursor is None
    
    def test_paginated_response_limit_one(self):
        """Test with limit of 1"""
        items = self.create_mock_items(5)
        
        def cursor_factory(item):
            return PaginationCursor(sort_index=item.sort_index, node_id=item.id).encode()
        
        response = create_paginated_response(items, limit=1, cursor_factory=cursor_factory)
        
        assert len(response.items) == 1
        assert response.has_more is True
        assert response.next_cursor is not None
    
    def test_paginated_response_with_total_count(self):
        """Test adding total count to response"""
        items = self.create_mock_items(5)
        response = create_paginated_response(items, limit=10, cursor_factory=None)
        response.total_count = 100
        
        assert response.total_count == 100


class TestParsePaginationParams:
    """Test parse_pagination_params function"""
    
    def test_parse_no_cursor_default_limit(self):
        """Test parsing with no cursor and default limit"""
        cursor, limit = parse_pagination_params(cursor_str=None, limit=50)
        
        assert cursor is None
        assert limit == 50
    
    def test_parse_with_valid_cursor(self):
        """Test parsing with valid cursor"""
        original_cursor = PaginationCursor(sort_index=100, node_id=200)
        encoded = original_cursor.encode()
        
        cursor, limit = parse_pagination_params(cursor_str=encoded, limit=50)
        
        assert cursor is not None
        assert cursor.sort_index == 100
        assert cursor.node_id == 200
        assert limit == 50
    
    def test_parse_limit_clamping_high(self):
        """Test that limit is clamped to max_limit"""
        cursor, limit = parse_pagination_params(
            cursor_str=None,
            limit=200,
            max_limit=100
        )
        assert limit == 100
    
    def test_parse_limit_clamping_low(self):
        """Test that limit is clamped to minimum of 1"""
        cursor, limit = parse_pagination_params(
            cursor_str=None,
            limit=0,
            max_limit=100
        )
        assert limit == 1
        
        cursor, limit = parse_pagination_params(
            cursor_str=None,
            limit=-10,
            max_limit=100
        )
        assert limit == 1
    
    def test_parse_invalid_cursor_format(self):
        """Test parsing invalid cursor format"""
        with pytest.raises(ValueError, match="Invalid cursor format"):
            parse_pagination_params(cursor_str="invalid-cursor", limit=50)
    
    def test_parse_corrupted_cursor(self):
        """Test parsing corrupted cursor data"""
        import base64
        # Valid base64 but invalid JSON structure
        bad_data = base64.urlsafe_b64encode(b'{"wrong": "format"}').decode().rstrip('=')
        
        with pytest.raises(ValueError):
            parse_pagination_params(cursor_str=bad_data, limit=50)
    
    def test_parse_custom_max_limit(self):
        """Test with custom max_limit"""
        cursor, limit = parse_pagination_params(
            cursor_str=None,
            limit=1000,
            max_limit=500
        )
        assert limit == 500


class TestPaginationEdgeCases:
    """Test edge cases and integration scenarios"""
    
    def test_full_pagination_flow(self):
        """Test full pagination flow: encode -> parse -> use"""
        # Create initial cursor
        cursor = PaginationCursor(sort_index=50, node_id=100)
        encoded = cursor.encode()
        
        # Parse parameters
        parsed_cursor, limit = parse_pagination_params(
            cursor_str=encoded,
            limit=25
        )
        
        assert parsed_cursor.sort_index == 50
        assert parsed_cursor.node_id == 100
        assert limit == 25
    
    def test_unicode_in_cursor_data(self):
        """Test that cursor handles unicode (if extended)"""
        # Current implementation only supports int values
        # but we test encoding/decoding integrity
        cursor = PaginationCursor(sort_index=12345, node_id=67890)
        encoded = cursor.encode()
        decoded = PaginationCursor.decode(encoded)
        assert decoded.sort_index == 12345
        assert decoded.node_id == 67890
    
    def test_large_scale_pagination_simulation(self):
        """Simulate pagination through large dataset"""
        items = [
            MockItem(id=i, sort_index=i * 100, name=f"Item {i}")
            for i in range(1000)
        ]
        
        def cursor_factory(item):
            return PaginationCursor(
                sort_index=item.sort_index,
                node_id=item.id
            ).encode()
        
        # Simulate fetching 10 pages
        all_fetched = []
        next_cursor = None
        
        for page in range(10):
            # Get page of items
            page_items = items[page * 10:(page + 1) * 10 + 1]  # +1 to check has_more
            
            response = create_paginated_response(
                page_items,
                limit=10,
                cursor_factory=cursor_factory
            )
            
            all_fetched.extend(response.items)
            
            if page < 9:  # Not last page
                assert response.has_more is True
                assert response.next_cursor is not None
                # Decode cursor to verify
                decoded = PaginationCursor.decode(response.next_cursor)
                assert decoded.sort_index == (page * 10 + 9) * 100
                assert decoded.node_id == page * 10 + 9
        
        assert len(all_fetched) == 100
    
    def test_paginated_response_generic_type(self):
        """Test that PaginatedResponse works with generic types"""
        from typing import List
        
        items: List[int] = [1, 2, 3, 4, 5]
        response = create_paginated_response(items, limit=10, cursor_factory=None)
        
        assert isinstance(response, PaginatedResponse)
        assert response.items == items
    
    def test_cursor_stability_across_operations(self):
        """Test cursor remains stable across multiple encode/decode cycles"""
        original = PaginationCursor(sort_index=42, node_id=99)
        
        # Multiple encode/decode cycles
        cursor = original
        for _ in range(10):
            encoded = cursor.encode()
            cursor = PaginationCursor.decode(encoded)
        
        assert cursor.sort_index == 42
        assert cursor.node_id == 99
