# interaction-confirmation-flow Specification

## Purpose
TBD - created by archiving change feishu-bot-ux-upgrade. Update Purpose after archive.
## Requirements
### Requirement: Risk level classification
The system SHALL classify all user-initiated actions into risk levels.

#### Scenario: Safe action execution
- **WHEN** user requests a safe action (e.g., show status, list workspaces)
- **THEN** action executes immediately without confirmation
- **AND** result is displayed in a card

#### Scenario: Guarded action execution
- **WHEN** user requests a guarded action (e.g., start session when at capacity)
- **THEN** system checks resource availability
- **AND** shows warning if resources are constrained
- **AND** user can proceed or cancel

#### Scenario: Confirm-required action
- **WHEN** user requests a high-risk action (e.g., stop session, switch workspace with unsaved changes)
- **THEN** system displays confirmation card
- **AND** action only proceeds after explicit confirmation

### Requirement: Confirmation dialog
The system SHALL present clear confirmation dialogs for risky operations.

#### Scenario: Confirmation card display
- **WHEN** confirmation is required
- **THEN** system sends interactive card showing:
  - Action description
  - Affected resources
- **AND** provides "确认" and "取消" buttons
- **AND** confirmation expires after 5 minutes

#### Scenario: Explicit confirmation
- **WHEN** user clicks "确认" button
- **THEN** system executes the action
- **AND** updates card to show execution started

#### Scenario: Cancellation
- **WHEN** user clicks "取消" button or sends "取消" text
- **THEN** action is aborted
- **AND** card is updated to show "已取消"

#### Scenario: Timeout
- **WHEN** confirmation is not received within 5 minutes
- **THEN** confirmation expires
- **AND** card is updated to show "已过期"
- **AND** user must re-initiate the action

### Requirement: Undo capability
The system SHALL provide undo for certain destructive actions where possible.

#### Scenario: Undo available
- **WHEN** action supports undo (e.g., stop session)
- **THEN** confirmation card shows "此操作可在 10 秒内撤销"
- **AND** result card provides "撤销" button for 10 seconds

#### Scenario: Undo execution
- **WHEN** user clicks "撤销" within time window
- **THEN** system reverses the action
- **AND** notifies user of successful undo

### Requirement: Confirmation bypass for trusted patterns
The system SHALL allow power users to bypass confirmations for specific patterns.

#### Scenario: Bypass flag
- **WHEN** user includes "--force" or "强制" in command
- **THEN** confirmation is skipped
- **AND** action executes immediately
- **AND** result indicates "已强制执行"

#### Scenario: Session-level bypass
- **WHEN** user has confirmed a pattern 3 times in same session
- **THEN** system offers "记住我的选择"
- **AND** future similar actions skip confirmation for this session

