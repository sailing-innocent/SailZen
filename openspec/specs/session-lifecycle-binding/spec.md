# session-lifecycle-binding Specification

## Purpose
TBD - created by archiving change feishu-bot-ux-upgrade. Update Purpose after archive.
## Requirements
### Requirement: Session state machine
The system SHALL maintain an explicit state machine for each OpenCode session.

#### Scenario: State transition to starting
- **WHEN** user initiates start command
- **THEN** session state transitions from `idle` to `starting`
- **AND** state change is persisted to disk

#### Scenario: State transition to running
- **WHEN** health check passes on starting session
- **THEN** session state transitions from `starting` to `running`
- **AND** card is updated to show "运行中" status

#### Scenario: State transition to stopping
- **WHEN** user initiates stop command
- **THEN** session state transitions from `running` to `stopping`
- **AND** new commands for this session are queued or rejected

#### Scenario: State transition to idle
- **WHEN** OpenCode process exits cleanly
- **THEN** session state transitions to `idle`
- **AND** session info is retained for restart

#### Scenario: Error state handling
- **WHEN** health check fails or process crashes unexpectedly
- **THEN** session state transitions to `error`
- **AND** error details are captured
- **AND** user is notified with recovery options

### Requirement: Bot lifecycle binding
The system SHALL bind OpenCode session lifecycle to the bot process lifecycle.

#### Scenario: Bot startup recovery
- **WHEN** bot process starts
- **THEN** system reads persisted session states from disk
- **AND** attempts to reconnect to any `running` sessions
- **AND** marks unrecoverable sessions as `error`

#### Scenario: Bot shutdown cleanup
- **WHEN** bot process receives shutdown signal
- **THEN** system gracefully stops all `running` and `starting` sessions
- **AND** waits up to 30 seconds for clean shutdown
- **AND** persists final session states to disk

#### Scenario: Unclean bot termination
- **WHEN** bot process crashes or is killed
- **THEN** on next startup, system detects stale sessions
- **AND** attempts recovery or marks as error with cleanup option

### Requirement: Session health monitoring
The system SHALL continuously monitor session health.

#### Scenario: Health check
- **WHEN** session is in `running` state
- **THEN** system periodically checks health endpoint
- **AND** transitions to `error` state if check fails 3 consecutive times

#### Scenario: Auto-recovery
- **WHEN** session enters `error` state
- **THEN** system attempts automatic restart (if auto_restart enabled)
- **AND** notifies user of recovery attempt

