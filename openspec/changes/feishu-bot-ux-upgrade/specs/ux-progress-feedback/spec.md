## ADDED Requirements

### Requirement: Operation progress indication
The system SHALL provide visual feedback for all operations taking longer than 1 second.

#### Scenario: Long operation starts
- **WHEN** an operation is expected to take >1 second
- **THEN** system immediately sends a "处理中" card
- **AND** card includes operation description and indeterminate progress indicator

#### Scenario: Determinate progress
- **WHEN** operation reports progress percentage
- **THEN** system updates progress card with percentage
- **AND** shows estimated time remaining if available

#### Scenario: Indeterminate progress
- **WHEN** operation duration is unknown
- **THEN** system shows animated spinner or "请稍候" text
- **AND** updates card every 5 seconds to show it's still alive

#### Scenario: Operation completion
- **WHEN** operation completes successfully
- **THEN** progress card transitions to result view
- **AND** color changes to green to indicate success

#### Scenario: Operation failure
- **WHEN** operation fails
- **THEN** progress card shows error details
- **AND** color changes to red
- **AND** provides retry/cancel options

### Requirement: Waiting state management
The system SHALL prevent user confusion during wait periods.

#### Scenario: Command during processing
- **WHEN** user sends command while another operation is in progress for same session
- **THEN** system queues the command or rejects with "当前有操作进行中" message
- **AND** shows estimated wait time if available

#### Scenario: Timeout indication
- **WHEN** operation exceeds expected duration
- **THEN** system updates card to show "比预期用时更长"
- **AND** provides option to cancel or continue waiting

### Requirement: Real-time status updates
The system SHALL update status displays as state changes occur.

#### Scenario: State change notification
- **WHEN** session state changes (e.g., starting → running)
- **THEN** status card is updated within 2 seconds
- **AND** visual indicator (color/icon) reflects new state

#### Scenario: Activity log
- **WHEN** session activities occur
- **THEN** they are appended to an activity log visible in status card
- **AND** log shows last 5 activities with timestamps
