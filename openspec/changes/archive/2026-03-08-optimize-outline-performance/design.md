## Context

The AI outline parsing feature in SailZen currently suffers from severe performance issues that cause page crashes. Through code analysis, the following critical bottlenecks were identified:

**Current Implementation Problems:**
1. **No Pagination**: `GET /outline/{id}/tree` loads ALL nodes at once via `get_outline_tree_impl()` which queries all `OutlineNode` records and builds the entire tree recursively in memory
2. **Evidence Text Overhead**: `ExtractedOutlineNode` includes `evidence_list` with full text content, but frontend only displays 100 characters. For 50 nodes with 500-char evidence each, this adds 25KB+ of unnecessary payload
3. **No Virtualization**: `outline_review_panel.tsx` renders ALL tree nodes to DOM simultaneously, causing browser lockup with large trees
4. **No Lazy Loading**: Entire outline tree loads when selecting an outline, regardless of how many nodes the user actually views
5. **WebSocket Payload Size**: Full extraction results sent via WebSocket including all node evidence

**Current Data Flow:**
```
Backend: DB → ORM → Full Tree Build → JSON Serialization → HTTP Response
Frontend: Parse JSON → Store All Nodes → Render All Nodes to DOM
```

**Problematic Code Locations:**
- `sail_server/infrastructure/orm/analysis/outline.py:384-430` - `get_outline_tree_impl()` loads entire tree
- `sail_server/application/dto/analysis.py:341-357` - `ExtractedOutlineNode` includes full evidence
- `packages/site/src/components/outline_review_panel.tsx` - renders all nodes without virtualization

## Goals / Non-Goals

**Goals:**
- Reduce initial page load time to under 1 second regardless of outline size
- Support outlines with 1000+ nodes without browser crashes
- Minimize memory footprint on frontend
- Maintain backward compatibility with existing APIs
- Implement pagination with configurable page sizes (default: 50 nodes)
- Truncate evidence text in list views (max 200 chars preview)
- Add lazy loading for node details and evidence
- Implement virtualization for tree rendering

**Non-Goals:**
- Database schema changes
- Modifying the AI extraction algorithm or batching strategy
- Changing the outline data model structure
- Adding client-side caching (can be future enhancement)
- Real-time collaboration features

## Decisions

**Decision 1: Cursor-Based Pagination for Tree Data**
- Use cursor-based pagination (not offset-based) for consistent ordering with hierarchical data
- Cursor combines `sort_index` and `node_id` for stable pagination across tree levels
- **Rationale**: Offset pagination breaks when tree structure changes during navigation; cursor pagination is stable and performant for tree data
- **Alternative considered**: Offset pagination - rejected due to instability with dynamic tree content

**Decision 2: Two-Stage Evidence Loading**
- Stage 1: List view returns truncated evidence preview (max 200 chars)
- Stage 2: Detail view fetches full evidence via separate endpoint `GET /outline/node/{id}/evidence`
- **Rationale**: Reduces initial payload by 80-90% while preserving full evidence access when needed
- **Alternative considered**: Always return full evidence - rejected due to performance impact

**Decision 3: Virtualized Tree with react-virtuoso**
- Use `react-virtuoso` library for virtualization (already used elsewhere in codebase)
- Render only visible nodes plus small overscan buffer
- Maintain virtual scroll position across pagination loads
- **Rationale**: Industry-standard solution, already in dependencies, handles dynamic heights well
- **Alternative considered**: react-window - rejected due to limited dynamic height support

**Decision 4: Flat List with Path-Based Hierarchy**
- Transform tree to flat list for virtualization
- Use `path` field (e.g., "1.2.3") to compute indentation and parent relationships
- **Rationale**: Flat lists virtualize efficiently; tree structures don't
- **Alternative considered**: Virtualized tree component - rejected due to complexity and limited library options

**Decision 5: Backend Node Expansion State Management**
- Store expanded node IDs in backend session/query state for pagination
- Include `is_expanded` flag in paginated responses
- **Rationale**: Ensures consistent view across pagination requests; avoids frontend tracking complexity
- **Alternative considered**: Frontend-only expansion tracking - rejected due to pagination complexity

## Risks / Trade-offs

**Risk: Breaking Changes to Existing API**
- Adding pagination to existing `/outline/{id}/tree` endpoint changes response format
- **Mitigation**: Make pagination opt-in via query params; return all nodes if no pagination params provided; mark old behavior as deprecated

**Risk: Increased Backend Complexity**
- Cursor-based pagination requires more complex SQL queries
- **Mitigation**: Encapsulate pagination logic in reusable utility; add comprehensive tests

**Risk: UX Degradation with Lazy Loading**
- Users may see loading spinners when expanding nodes for evidence
- **Mitigation**: Add skeleton screens; preload evidence for likely-to-expand nodes; cache evidence client-side

**Risk: Virtualization Accessibility Issues**
- Screen readers may struggle with virtualized content
- **Mitigation**: Use proper ARIA labels; ensure keyboard navigation works; test with screen readers

**Risk: Tree Reordering Complexity**
- Flat list approach requires careful handling of drag-and-drop or reordering operations
- **Mitigation**: Keep tree structure in memory for edits; only flatten for display; preserve `path` field updates

## Migration Plan

**Phase 1: Backend Pagination (Week 1)**
1. Create new paginated endpoint `/outline/{id}/nodes` with cursor-based pagination
2. Add lazy loading endpoint `/outline/node/{id}/evidence`
3. Update DTOs to include evidence preview (truncated) vs full evidence
4. Add deprecation notice to existing `/outline/{id}/tree` endpoint

**Phase 2: Frontend Virtualization (Week 2)**
1. Implement virtualized list component with react-virtuoso
2. Create flat list transformation utility
3. Add pagination state management
4. Implement lazy evidence loading on node expand

**Phase 3: Integration & Testing (Week 3)**
1. Update outline panels to use new endpoints
2. Add loading states and error handling
3. Performance testing with large outlines (1000+ nodes)
4. Accessibility audit

**Rollback Strategy:**
- Keep old endpoints functional with feature flags
- Frontend can toggle between old/new implementations
- Database schema unchanged - no rollback needed

## Open Questions

**Q1: Should we implement client-side caching for evidence?**
- A: Start without; add if performance testing shows evidence loading is too slow

**Q2: How to handle deep trees (>10 levels) with flat list approach?**
- A: Implement max indentation (e.g., 8 levels visible) with "Show more" expansion

**Q3: Should pagination be configurable per outline?**
- A: Start with global default (50); consider per-outline config if needed

**Q4: How to handle search/filter in virtualized list?**
- A: Search filters server-side; virtualization renders filtered results

**Q5: Should we compress evidence text in database?**
- A: Not in scope; current optimization focuses on API layer
