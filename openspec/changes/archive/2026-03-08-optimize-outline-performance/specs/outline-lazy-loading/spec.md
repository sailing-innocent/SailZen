## ADDED Requirements

### Requirement: Lazy loading of node evidence
The system SHALL provide on-demand loading of full evidence text for individual nodes.

#### Scenario: Load evidence for specific node
- **WHEN** client requests `GET /outline/node/{id}/evidence`
- **THEN** system SHALL return full `evidence_list` array for that node
- **AND** response SHALL complete within 100ms

#### Scenario: Evidence caching headers
- **WHEN** evidence endpoint returns response
- **THEN** response SHALL include appropriate cache headers
- **AND** etag SHALL be based on evidence content hash

#### Scenario: Handle nodes without evidence
- **WHEN** evidence is requested for node with no evidence
- **THEN** system SHALL return empty array with 200 status
- **AND** response SHALL include `evidence_count: 0`

### Requirement: Lazy loading of node details
The system SHALL support fetching detailed node information separately from list views.

#### Scenario: Load full node details
- **WHEN** client requests `GET /outline/node/{id}`
- **THEN** system SHALL return complete node data including full summary and metadata
- **AND** response SHALL include computed fields like `child_count`

#### Scenario: Batch load multiple node details
- **WHEN** client requests `POST /outline/nodes/details` with array of node IDs
- **THEN** system SHALL return details for all requested nodes
- **AND** response SHALL complete within 200ms for up to 50 nodes
