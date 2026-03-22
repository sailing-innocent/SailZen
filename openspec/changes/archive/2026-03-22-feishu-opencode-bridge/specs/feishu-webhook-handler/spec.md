## ADDED Requirements

### Requirement: Feishu Bot receives and validates webhook events
The system SHALL receive and validate incoming webhook events from Feishu Open Platform.

#### Scenario: Valid signature verification
- **WHEN** Feishu sends a message event with valid signature and timestamp
- **THEN** the system SHALL accept the event and return HTTP 200
- **AND** the system SHALL parse the message content for further processing

#### Scenario: Invalid signature rejection
- **WHEN** a request arrives with invalid signature or expired timestamp (>5 minutes)
- **THEN** the system SHALL return HTTP 403 Forbidden
- **AND** the system SHALL log the security event

### Requirement: Feishu Bot parses user commands
The system SHALL parse both structured commands and natural language from user messages.

#### Scenario: Structured command recognition
- **WHEN** user sends "/git-pull main"
- **THEN** the system SHALL recognize command type as "git"
- **AND** the system SHALL extract action "pull" and argument "main"

#### Scenario: Remote control command recognition
- **WHEN** user sends "/start-opencode /work/myproject"
- **THEN** the system SHALL recognize command type as "remote-control"
- **AND** the system SHALL extract action "start-opencode"
- **AND** the system SHALL extract project path "/work/myproject"

#### Scenario: Status query command
- **WHEN** user sends "/status"
- **THEN** the system SHALL recognize command type as "query"
- **AND** the system SHALL extract query type "status"
- **AND** the system SHALL prepare to fetch current system state

#### Scenario: Natural language intent recognition
- **WHEN** user sends "帮我拉取main分支的最新代码"
- **THEN** the system SHALL identify intent as "git-pull"
- **AND** the system SHALL extract target branch "main"

#### Scenario: Multi-line command handling
- **WHEN** user sends a message with multiple lines starting with "/"
- **THEN** the system SHALL treat each line as a separate command
- **AND** the system SHALL execute them sequentially

### Requirement: Feishu Bot handles @mentions in group chats
The system SHALL respond only to messages that @mention the bot in group chats.

#### Scenario: Group chat mention
- **WHEN** a message in group chat contains @mention of the bot
- **THEN** the system SHALL process the message
- **AND** the system SHALL reply to the group chat

#### Scenario: Group chat without mention
- **WHEN** a message in group chat does NOT @mention the bot
- **THEN** the system SHALL ignore the message
- **AND** the system SHALL NOT generate any response

### Requirement: Feishu Bot sends interactive card messages
The system SHALL send interactive card messages for better user experience.

#### Scenario: Task progress card
- **WHEN** a long-running task is initiated
- **THEN** the system SHALL send an interactive card with progress indicator
- **AND** the system SHALL update the card periodically with status changes

#### Scenario: Confirmation card for sensitive operations
- **WHEN** user requests a sensitive operation (e.g., git push to main)
- **THEN** the system SHALL send a confirmation card with "Confirm" and "Cancel" buttons
- **AND** the system SHALL only proceed after user confirms
