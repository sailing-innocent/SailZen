## Why

The AI outline parsing feature currently causes page crashes and severe performance degradation. Analysis reveals that the system loads ALL outline nodes with full evidence text at once, transmitting massive payloads that overwhelm the browser. For large novels with 50+ outline nodes, each containing kilobytes of evidence text, the page becomes unresponsive and may crash when entering the outline view.

## What Changes

- **Backend**: Implement pagination for outline tree API with chunked loading and evidence text truncation
- **Backend**: Add lazy loading endpoints for node details and evidence text
- **Backend**: Optimize DTOs to exclude full evidence text in list views
- **Frontend**: Implement virtualized list rendering for outline tree
- **Frontend**: Add progressive loading with infinite scroll
- **Frontend**: Lazy load evidence text only when nodes are expanded
- **Performance**: Add payload size limits and loading states

## Capabilities

### New Capabilities
- `outline-pagination`: Server-side pagination for outline tree data with configurable page sizes
- `outline-lazy-loading`: On-demand loading of node details and evidence text
- `outline-virtualization`: Frontend virtualization for rendering large outline trees efficiently

### Modified Capabilities
- *None - existing specs don't cover outline data loading patterns*

## Impact

- **Backend APIs**: `GET /outline/{id}/tree` will support pagination parameters; new endpoints for lazy loading
- **Frontend Components**: `outline_panel.tsx`, `outline_review_panel.tsx` - major refactoring for virtualization
- **DTOs**: `ExtractedOutlineNode` - evidence text truncation in list views
- **Database**: No schema changes required
- **User Experience**: Outline pages will load instantly regardless of outline size
