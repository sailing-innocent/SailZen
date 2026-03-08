## ADDED Requirements

### Requirement: Server-side pagination for outline tree
The system SHALL support cursor-based pagination for retrieving outline nodes to prevent loading entire trees into memory.

#### Scenario: Request first page of nodes
- **WHEN** client requests outline nodes with `limit=50` and no cursor
- **THEN** system SHALL return first 50 nodes ordered by `sort_index`
- **AND** response SHALL include `next_cursor` for fetching subsequent pages
- **AND** response SHALL include `has_more` boolean flag

#### Scenario: Request subsequent pages
- **WHEN** client requests nodes with `cursor={last_sort_index},{last_node_id}` and `limit=50`
- **THEN** system SHALL return next 50 nodes after the cursor position
- **AND** nodes SHALL maintain stable ordering across pagination requests

#### Scenario: Paginate with parent filtering
- **WHEN** client requests nodes with `parent_id={id}` and pagination params
- **THEN** system SHALL return paginated children of specified parent only
- **AND** pagination SHALL work within subtree scope

#### Scenario: Handle large outlines efficiently
- **WHEN** outline contains 1000+ nodes
- **THEN** paginated endpoint SHALL return first page in under 200ms
- **AND** memory usage SHALL remain constant regardless of total node count

### Requirement: Evidence text truncation
The system SHALL truncate evidence text in list view responses while preserving full evidence accessibility.

#### Scenario: List view returns truncated evidence
- **WHEN** outline nodes are returned in paginated list view
- **THEN** each node's `evidence_preview` SHALL contain maximum 200 characters
- **AND** `evidence_full_available` flag SHALL indicate if full text exists

#### Scenario: Full evidence excluded from list response
- **WHEN** list view is requested without `include_full_evidence=true`
- **THEN** response SHALL NOT include `evidence_list` field
- **AND** payload size SHALL be reduced by at least 70% compared to full response
