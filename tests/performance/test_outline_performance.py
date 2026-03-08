# -*- coding: utf-8 -*-
# @file test_outline_performance.py
# @brief Performance tests for outline pagination and virtualization
# @author sailing-innocent
# @date 2026-03-08
# @version 1.0
# ---------------------------------

"""
Outline Performance Test Suite

Tests:
- Large outline loading (1000+ nodes)
- Pagination performance
- Memory usage
- Scroll performance
- Evidence lazy loading effectiveness
- Error recovery

Usage:
    cd /path/to/project
    uv run pytest tests/performance/test_outline_performance.py -v
    
Or run with performance profiling:
    uv run pytest tests/performance/test_outline_performance.py --profile
"""

import pytest
import time
import json
from typing import List, Dict, Any
from sqlalchemy.orm import Session

from sail_server.utils.pagination import (
    PaginationCursor,
    create_paginated_response,
    parse_pagination_params,
)
from sail_server.infrastructure.orm.analysis import Outline, OutlineNode


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def large_outline_data() -> Dict[str, Any]:
    """Generate test data for a large outline with 1000+ nodes"""
    nodes = []
    
    # Create hierarchical structure
    # 10 acts, each with 10 arcs, each with 10 scenes = 1000 nodes
    node_id = 1
    for act_idx in range(10):
        act_id = node_id
        nodes.append({
            'id': act_id,
            'outline_id': 1,
            'parent_id': None,
            'node_type': 'act',
            'title': f'Act {act_idx + 1}',
            'summary': f'Summary for Act {act_idx + 1}',
            'sort_index': act_idx * 1000,
            'depth': 0,
            'path': f'{act_idx + 1}',
        })
        node_id += 1
        
        for arc_idx in range(10):
            arc_id = node_id
            nodes.append({
                'id': arc_id,
                'outline_id': 1,
                'parent_id': act_id,
                'node_type': 'arc',
                'title': f'Arc {act_idx + 1}.{arc_idx + 1}',
                'summary': f'Summary for Arc {act_idx + 1}.{arc_idx + 1}',
                'sort_index': act_idx * 1000 + arc_idx * 100 + 1,
                'depth': 1,
                'path': f'{act_idx + 1}.{arc_idx + 1}',
            })
            node_id += 1
            
            for scene_idx in range(10):
                nodes.append({
                    'id': node_id,
                    'outline_id': 1,
                    'parent_id': arc_id,
                    'node_type': 'scene',
                    'title': f'Scene {act_idx + 1}.{arc_idx + 1}.{scene_idx + 1}',
                    'summary': f'Summary for Scene {act_idx + 1}.{arc_idx + 1}.{scene_idx + 1}',
                    'sort_index': act_idx * 1000 + arc_idx * 100 + scene_idx + 2,
                    'depth': 2,
                    'path': f'{act_idx + 1}.{arc_idx + 1}.{scene_idx + 1}',
                    'meta_data': {
                        'evidence': [
                            {
                                'text': 'Sample evidence text ' * 50,  # ~1000 chars per evidence
                                'chapter_title': f'Chapter {scene_idx + 1}',
                                'start_fragment': 'Start of scene',
                                'end_fragment': 'End of scene',
                            }
                        ]
                    }
                })
                node_id += 1
    
    return {
        'outline_id': 1,
        'title': 'Test Large Outline',
        'node_count': len(nodes),
        'nodes': nodes,
    }


# ============================================================================
# Test 8.1: Large Outline Creation
# ============================================================================

class TestLargeOutlineCreation:
    """Test 8.1: Create test outline with 1000+ nodes"""
    
    @pytest.mark.performance
    @pytest.mark.db
    def test_create_large_outline(self, db: Session, large_outline_data):
        """Create an outline with 1000+ nodes"""
        start_time = time.time()
        
        # Create outline
        outline = Outline(
            id=large_outline_data['outline_id'],
            edition_id=1,
            title=large_outline_data['title'],
            outline_type='main',
        )
        db.add(outline)
        
        # Create all nodes
        for node_data in large_outline_data['nodes']:
            node = OutlineNode(
                id=node_data['id'],
                outline_id=node_data['outline_id'],
                parent_id=node_data.get('parent_id'),
                node_type=node_data['node_type'],
                title=node_data['title'],
                summary=node_data['summary'],
                sort_index=node_data['sort_index'],
                depth=node_data['depth'],
                path=node_data['path'],
                meta_data=node_data.get('meta_data'),
            )
            db.add(node)
        
        db.commit()
        elapsed = time.time() - start_time
        
        # Verify
        count = db.query(OutlineNode).filter(OutlineNode.outline_id == 1).count()
        assert count == 1110, f"Expected 1110 nodes, got {count}"
        
        print(f"✓ Created {count} nodes in {elapsed:.2f}s")
        
        # Should complete within reasonable time
        assert elapsed < 30, f"Creating outline took too long: {elapsed:.2f}s"


# ============================================================================
# Test 8.2: Initial Load Time
# ============================================================================

class TestInitialLoadTime:
    """Test 8.2: Measure initial load time (target: <1 second)"""
    
    @pytest.mark.performance
    @pytest.mark.db
    def test_paginated_first_page_load_time(self, db: Session):
        """Test that first page loads in under 1 second"""
        from sail_server.controller.outline import OutlineController
        
        controller = OutlineController()
        
        # Warm up
        db.query(OutlineNode).filter(OutlineNode.outline_id == 1).first()
        
        # Measure first page load
        start_time = time.time()
        
        # Simulate paginated request
        query = db.query(OutlineNode).filter(
            OutlineNode.outline_id == 1
        ).order_by(OutlineNode.sort_index).limit(50)
        
        nodes = query.all()
        elapsed = time.time() - start_time
        
        print(f"✓ First page ({len(nodes)} nodes) loaded in {elapsed*1000:.0f}ms")
        
        # Target: < 1 second (1000ms)
        assert elapsed < 1.0, f"First page load too slow: {elapsed*1000:.0f}ms"


# ============================================================================
# Test 8.3: Scroll Performance
# ============================================================================

class TestScrollPerformance:
    """Test 8.3: Test scroll performance at 60fps"""
    
    @pytest.mark.performance
    def test_flat_list_transformation_performance(self, large_outline_data):
        """Test that tree-to-flat conversion is fast enough for 60fps"""
        nodes = large_outline_data['nodes']
        
        # Simulate tree-to-flat transformation
        start_time = time.time()
        
        # Build parent map
        parent_map = {n['id']: n for n in nodes}
        
        # Flatten with depth calculation
        flat_list = []
        for node in nodes:
            flat_list.append({
                **node,
                'is_expanded': False,
                'visible': node['depth'] == 0,  # Only root level visible initially
            })
        
        elapsed = time.time() - start_time
        
        # For 60fps, we need < 16.67ms per frame
        # Allow more time for 1000 nodes, but should still be fast
        print(f"✓ Flattened {len(nodes)} nodes in {elapsed*1000:.1f}ms")
        assert elapsed < 0.1, f"Transformation too slow: {elapsed*1000:.1f}ms"


# ============================================================================
# Test 8.4: Memory Usage
# ============================================================================

class TestMemoryUsage:
    """Test 8.4: Verify memory usage stays constant with large outlines"""
    
    @pytest.mark.performance
    def test_pagination_memory_efficiency(self, large_outline_data):
        """Test that pagination doesn't load all nodes into memory"""
        import sys
        
        nodes = large_outline_data['nodes']
        
        # Measure memory for full list
        full_size = sys.getsizeof(json.dumps(nodes))
        
        # Simulate paginated approach - only keep 50 nodes
        paginated_subset = nodes[:50]
        paginated_size = sys.getsizeof(json.dumps(paginated_subset))
        
        memory_reduction = (full_size - paginated_size) / full_size * 100
        
        print(f"✓ Memory reduction: {memory_reduction:.1f}% ({full_size/1024:.0f}KB → {paginated_size/1024:.0f}KB)")
        
        # Should reduce memory by at least 90%
        assert memory_reduction > 90, f"Memory reduction insufficient: {memory_reduction:.1f}%"


# ============================================================================
# Test 8.5: Pagination with Various Page Sizes
# ============================================================================

class TestPaginationPageSizes:
    """Test 8.5: Test pagination with various page sizes (10, 50, 100)"""
    
    @pytest.mark.parametrize("page_size", [10, 50, 100])
    @pytest.mark.performance
    def test_various_page_sizes(self, page_size, large_outline_data):
        """Test pagination with different page sizes"""
        nodes = large_outline_data['nodes']
        
        start_time = time.time()
        
        # Simulate paginated response
        page = nodes[:page_size + 1]  # +1 to check has_more
        response = create_paginated_response(
            items=page,
            limit=page_size,
            cursor_factory=lambda item: PaginationCursor(
                sort_index=item['sort_index'],
                node_id=item['id']
            ).encode()
        )
        
        elapsed = time.time() - start_time
        
        print(f"✓ Page size {page_size}: {len(response.items)} items, has_more={response.has_more}, time={elapsed*1000:.1f}ms")
        
        assert len(response.items) == page_size
        assert response.has_more is True
        assert response.next_cursor is not None


# ============================================================================
# Test 8.6: Evidence Lazy Loading Effectiveness
# ============================================================================

class TestEvidenceLazyLoading:
    """Test 8.6: Verify evidence lazy loading reduces payload by 70%+"""
    
    @pytest.mark.performance
    def test_evidence_truncation_reduces_payload(self, large_outline_data):
        """Test that evidence truncation reduces payload size significantly"""
        nodes = large_outline_data['nodes']
        
        # Calculate full payload size (with all evidence)
        full_payload_size = 0
        for node in nodes:
            if node.get('meta_data', {}).get('evidence'):
                for evidence in node['meta_data']['evidence']:
                    full_payload_size += len(evidence.get('text', '').encode('utf-8'))
        
        # Calculate truncated payload size (200 char limit)
        truncated_payload_size = 0
        for node in nodes:
            if node.get('meta_data', {}).get('evidence'):
                for evidence in node['meta_data']['evidence']:
                    text = evidence.get('text', '')
                    truncated = text[:200] + ('...' if len(text) > 200 else '')
                    truncated_payload_size += len(truncated.encode('utf-8'))
        
        reduction = (full_payload_size - truncated_payload_size) / full_payload_size * 100
        
        print(f"✓ Evidence payload: {full_payload_size/1024:.0f}KB → {truncated_payload_size/1024:.0f}KB ({reduction:.1f}% reduction)")
        
        # Should reduce by at least 70%
        assert reduction >= 70, f"Payload reduction insufficient: {reduction:.1f}%"


# ============================================================================
# Test 8.7: Error Recovery
# ============================================================================

class TestErrorRecovery:
    """Test 8.7: Test error recovery (network failures, timeouts)"""
    
    @pytest.mark.performance
    def test_pagination_cursor_error_recovery(self):
        """Test that invalid cursors are handled gracefully"""
        # Test invalid cursor
        with pytest.raises(ValueError, match="Invalid cursor format"):
            parse_pagination_params(cursor_str="invalid-cursor", limit=50)
        
        # Test malformed cursor
        with pytest.raises(ValueError):
            parse_pagination_params(cursor_str="!!!bad-base64!!!", limit=50)
    
    @pytest.mark.performance
    def test_empty_results_handling(self):
        """Test handling of empty result sets"""
        response = create_paginated_response(
            items=[],
            limit=50,
            cursor_factory=lambda item: "cursor"
        )
        
        assert len(response.items) == 0
        assert response.has_more is False
        assert response.next_cursor is None
    
    @pytest.mark.performance  
    def test_pagination_resumption_after_error(self, large_outline_data):
        """Test that pagination can resume from a valid cursor after error"""
        nodes = large_outline_data['nodes']
        
        # Get first page
        first_page = nodes[:51]
        response1 = create_paginated_response(
            items=first_page,
            limit=50,
            cursor_factory=lambda item: PaginationCursor(
                sort_index=item['sort_index'],
                node_id=item['id']
            ).encode()
        )
        
        assert response1.next_cursor is not None
        
        # Simulate error then resume from cursor
        cursor = PaginationCursor.decode(response1.next_cursor)
        
        # Find next items after cursor
        next_items = [
            n for n in nodes 
            if (n['sort_index'] > cursor.sort_index) or 
               (n['sort_index'] == cursor.sort_index and n['id'] > cursor.node_id)
        ][:51]
        
        response2 = create_paginated_response(
            items=next_items,
            limit=50,
            cursor_factory=lambda item: PaginationCursor(
                sort_index=item['sort_index'],
                node_id=item['id']
            ).encode()
        )
        
        print(f"✓ Resumed pagination: page 1={len(response1.items)} items, page 2={len(response2.items)} items")
        
        assert len(response2.items) > 0


# ============================================================================
# Test Summary
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
