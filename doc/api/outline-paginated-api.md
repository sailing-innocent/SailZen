# Outline API Documentation

## Performance Optimized Endpoints

### List Outline Nodes (Paginated)

**Endpoint:** `GET /api/v1/analysis/outline/{outline_id}/nodes`

**Description:** Retrieves outline nodes with cursor-based pagination for efficient loading of large outlines.

**Parameters:**
- `outline_id` (path): The ID of the outline to fetch nodes from
- `limit` (query, optional): Number of nodes per page (1-100, default: 50)
- `cursor` (query, optional): Pagination cursor for fetching next page
- `parent_id` (query, optional): Filter nodes by parent ID

**Response:**
```json
{
  "nodes": [
    {
      "id": "string",
      "outline_id": "string",
      "parent_id": "string | null",
      "node_type": "string",
      "title": "string",
      "summary": "string | null",
      "significance": "string",
      "sort_index": 0,
      "depth": 0,
      "path": "string",
      "has_children": true,
      "evidence_preview": "string | null",
      "evidence_full_available": true,
      "events_count": 0
    }
  ],
  "next_cursor": "string | null",
  "has_more": true,
  "total_count": 100
}
```

**Features:**
- Evidence text truncated to 200 characters in list view
- `evidence_full_available` flag indicates if full evidence exists
- Cursor-based pagination for stable ordering

### Get Node Evidence

**Endpoint:** `GET /api/v1/analysis/outline/node/{node_id}/evidence`

**Description:** Retrieves full evidence text for a specific node (lazy loading).

**Parameters:**
- `node_id` (path): The ID of the node

**Response:**
```json
{
  "node_id": "string",
  "evidence_list": [
    {
      "text": "string",
      "chapter_title": "string | null",
      "start_fragment": "string | null",
      "end_fragment": "string | null"
    }
  ],
  "total_count": 0
}
```

### Get Node Detail

**Endpoint:** `GET /api/v1/analysis/outline/node/{node_id}/detail`

**Description:** Retrieves complete node details including metadata and events.

**Parameters:**
- `node_id` (path): The ID of the node

**Response:**
```json
{
  "id": "string",
  "outline_id": "string",
  "parent_id": "string | null",
  "node_type": "string",
  "title": "string",
  "summary": "string | null",
  "significance": "string",
  "sort_index": 0,
  "depth": 0,
  "path": "string",
  "chapter_start_id": "string | null",
  "chapter_end_id": "string | null",
  "meta_data": {},
  "events": [],
  "child_count": 0
}
```

### Batch Get Node Details

**Endpoint:** `POST /api/v1/analysis/outline/nodes/batch-details`

**Description:** Retrieves details for multiple nodes in a single request (max 50).

**Request Body:**
```json
["node_id_1", "node_id_2", ...]
```

**Response:** Array of node detail objects

## Legacy Endpoint (Deprecated)

### Get Full Outline Tree

**Endpoint:** `GET /api/v1/analysis/outline/{outline_id}/tree`

**Status:** ⚠️ Deprecated - Use paginated endpoints instead

**Note:** This endpoint loads the entire tree including all evidence text, which can cause performance issues with large outlines. Please migrate to the paginated `/nodes` endpoint.

## Cursor Format

Pagination cursors are base64-encoded JSON objects containing:
- `si` (sort_index): The sort index of the last item
- `ni` (node_id): The ID of the last item

Example cursor: `eyJzaSI6IDUwLCAibmkiOiAxMjN9`

## Performance Benefits

1. **Reduced Payload**: Evidence text truncated to 200 characters in list views (~70% reduction)
2. **Pagination**: Load nodes in batches of 50 instead of all at once
3. **Lazy Loading**: Evidence only loaded when explicitly requested
4. **Virtualization**: Frontend renders only visible nodes for smooth scrolling with 1000+ nodes

## Migration Guide

### From Legacy Tree Endpoint

**Before:**
```javascript
const tree = await api_get_outline_tree(outlineId)
// tree.nodes contains ALL nodes with FULL evidence
```

**After:**
```javascript
// Load first page of nodes
const response = await api_get_outline_nodes_paginated(outlineId, 50)
const nodes = response.nodes

// Load more pages as needed
if (response.has_more) {
  const nextPage = await api_get_outline_nodes_paginated(
    outlineId, 
    50, 
    response.next_cursor
  )
}

// Load evidence on-demand
const evidence = await api_get_node_evidence(nodeId)
```
