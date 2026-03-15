## ADDED Requirements

### Requirement: Quick weight recording
The user SHALL be able to quickly record their weight with minimal steps.

#### Scenario: Record current weight
- **WHEN** the user opens the app
- **THEN** they see a prominent weight input on the home screen
- **WHEN** they enter a weight value (e.g., 70.5 kg)
- **AND** tap the save button
- **THEN** the weight is saved locally
- **AND** the record appears in the recent list

#### Scenario: Record with timestamp
- **WHEN** the user records a weight
- **THEN** the current timestamp is automatically attached
- **AND** the user can optionally select a different date/time

### Requirement: Weight history list
The user SHALL be able to view their weight history in a chronological list.

#### Scenario: View recent records
- **WHEN** the user navigates to the weight screen
- **THEN** they see a list of weight records
- **AND** records are sorted by date (newest first)
- **AND** each record displays weight value and date

#### Scenario: Load more records
- **WHEN** the user scrolls to the bottom of the list
- **THEN** older records are loaded (pagination)
- **AND** a loading indicator is shown during fetch

### Requirement: Weight statistics
The app SHALL display weight statistics including average and trend.

#### Scenario: View statistics
- **WHEN** the user is on the weight screen
- **THEN** they see summary statistics: average weight, min, max, total records
- **AND** the period can be changed (7 days, 30 days, all time)

### Requirement: Weight trend chart
The app SHALL display a line chart showing weight trend over time.

#### Scenario: View trend chart
- **WHEN** the user is on the weight screen
- **THEN** they see a line chart with weight values on Y-axis and dates on X-axis
- **AND** the chart updates when new data is recorded
- **AND** the chart supports pinch-to-zoom (optional)

#### Scenario: Chart time range
- **WHEN** the user selects a time range (7d, 30d, 90d, all)
- **THEN** the chart updates to show data for that period

### Requirement: Edit and delete records
The user SHALL be able to edit or delete weight records.

#### Scenario: Edit record
- **WHEN** the user long-presses a weight record
- **THEN** an edit dialog appears
- **WHEN** they modify the weight value
- **AND** confirm
- **THEN** the record is updated locally

#### Scenario: Delete record
- **WHEN** the user swipes left on a record
- **THEN** a delete button appears
- **WHEN** they tap delete
- **AND** confirm the deletion
- **THEN** the record is removed locally

