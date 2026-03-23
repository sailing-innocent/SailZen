## ADDED Requirements

### Requirement: Real-time session observability
The system SHALL expose current session health, progress, recent events, and failure state for each active remote development session.

#### Scenario: Operator views active session cockpit
- **WHEN** the operator opens a session status view
- **THEN** the system displays current phase, latest activity, recent events, error summary, and actionable next steps for that session

#### Scenario: Session becomes stale
- **WHEN** a session exceeds the configured inactivity or heartbeat threshold
- **THEN** the system marks it as stale and surfaces an alert to the operator

### Requirement: Historical event and audit timeline
The system SHALL persist an event timeline for remote development sessions, including lifecycle changes, task events, user actions, and error transitions.

#### Scenario: Operator investigates a failure
- **WHEN** the operator asks why a session failed or stopped
- **THEN** the system returns a chronological summary of the relevant events, including the last successful step and the recorded failure cause

#### Scenario: Operator reviews manual actions
- **WHEN** the operator requests recent control actions for a session or workspace
- **THEN** the system returns the action history with initiator, action type, timestamp, and outcome

### Requirement: Actionable alerts and recovery affordances
The system SHALL pair alerts with direct recovery or acknowledgment actions when the underlying issue is operator-actionable.

#### Scenario: Desktop agent disconnects
- **WHEN** the desktop agent heartbeat is missing beyond the configured threshold
- **THEN** the system raises an offline alert and provides actions to refresh, inspect, or defer recovery

#### Scenario: Repeated session restart failures occur
- **WHEN** automated recovery fails repeatedly for the same session
- **THEN** the system escalates the issue and offers manual restart, log inspection, or disable-retry actions
