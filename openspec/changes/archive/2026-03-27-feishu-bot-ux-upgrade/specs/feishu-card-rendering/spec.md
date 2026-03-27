## ADDED Requirements

### Requirement: Card template system
The system SHALL provide a template system for rendering different types of Feishu message cards.

#### Scenario: Workspace selection card
- **WHEN** user requests to start a session or list workspaces
- **THEN** system displays an interactive card showing available workspaces with icons, status badges, and action buttons

#### Scenario: Session status card
- **WHEN** user requests status or a session state changes
- **THEN** system displays a card showing current session state (idle/starting/running/error), workspace info, port, and available actions

#### Scenario: Task progress card
- **WHEN** a long-running task starts
- **THEN** system displays a card with task description and progress indicator
- **AND** updates the same card when progress changes or task completes

#### Scenario: Confirmation dialog card
- **WHEN** a confirm-required action is initiated
- **THEN** system displays a card explaining the action, showing risk level, and providing Confirm/Cancel buttons

### Requirement: Card update mechanism
The system SHALL support updating existing cards instead of sending new messages.

#### Scenario: Progress update
- **WHEN** task progress changes
- **THEN** system updates the existing progress card with new information
- **AND** message_id remains the same

#### Scenario: Result update
- **WHEN** a task completes
- **THEN** system updates the progress card to show final results
- **AND** changes card color based on success/failure status

### Requirement: Card fallback to text
The system SHALL gracefully fallback to plain text when card rendering fails.

#### Scenario: Card API failure
- **WHEN** card message API returns error
- **THEN** system sends plain text message with same content
- **AND** logs the card rendering failure for debugging

### Requirement: Mobile-optimized card layout
All cards SHALL be optimized for mobile viewing on Feishu mobile app.

#### Scenario: Mobile viewing
- **WHEN** user views card on mobile device
- **THEN** all content is readable without horizontal scrolling
- **AND** buttons are large enough for touch interaction
- **AND** critical information is visible above the fold
