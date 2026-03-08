## ADDED Requirements

### Requirement: Virtualized list rendering
The system SHALL render outline trees using virtualization to handle large node counts without browser performance degradation.

#### Scenario: Render 1000 nodes with virtualization
- **WHEN** outline contains 1000 nodes
- **THEN** DOM SHALL contain maximum 20 visible node elements plus overscan buffer
- **AND** scroll performance SHALL maintain 60fps
- **AND** initial render SHALL complete within 100ms

#### Scenario: Virtual scroll with dynamic heights
- **WHEN** nodes have varying content heights (summary length varies)
- **THEN** virtualizer SHALL measure and cache element heights
- **AND** scroll position SHALL remain stable during content load

#### Scenario: Expand/collapse in virtualized list
- **WHEN** user expands a node to show children
- **THEN** virtualizer SHALL recalculate total height
- **AND** scroll position SHALL adjust smoothly without jumping

### Requirement: Progressive loading with infinite scroll
The system SHALL implement infinite scroll pattern for loading paginated data progressively.

#### Scenario: Auto-load on scroll near bottom
- **WHEN** user scrolls within 200px of list bottom
- **AND** more nodes are available (`has_more=true`)
- **THEN** system SHALL automatically fetch next page
- **AND** loading indicator SHALL display during fetch

#### Scenario: Manual load more option
- **WHEN** infinite scroll is disabled or user prefers manual loading
- **THEN** "Load more" button SHALL be available at list bottom
- **AND** button SHALL be disabled while loading

#### Scenario: Preserve scroll position across loads
- **WHEN** new page loads and appends to list
- **THEN** user's current scroll position SHALL be maintained
- **AND** newly loaded items SHALL appear below viewport if user was reading above

### Requirement: Flat list transformation for tree display
The system SHALL transform hierarchical tree data to flat list for efficient virtualization.

#### Scenario: Flatten tree with path-based hierarchy
- **WHEN** tree data contains nested parent-child relationships
- **THEN** system SHALL produce flat array ordered by tree traversal
- **AND** each item SHALL include `depth` and `path` fields for indentation
- **AND** parent-child relationships SHALL be computable from `path`

#### Scenario: Handle deeply nested trees
- **WHEN** tree contains nodes at depth > 10
- **THEN** flat list SHALL support arbitrary depth levels
- **AND** UI SHALL implement max visible depth with expansion option
