## ADDED Requirements

### Requirement: System creates and manages OpenCode sessions
The system SHALL create, track, and manage OpenCode sessions lifecycle.

#### Scenario: New session creation
- **WHEN** user sends a code generation request
- **THEN** the system SHALL create a new OpenCode session
- **AND** the system SHALL associate it with the user's current project
- **AND** the system SHALL return a session ID

#### Scenario: Single session enforcement
- **WHEN** user has an active session and requests a new one
- **THEN** the system SHALL warn the user about existing active session
- **AND** the system SHALL ask whether to abort existing or queue new request

#### Scenario: Session timeout handling
- **WHEN** a session has been idle for 30 minutes
- **THEN** the system SHALL mark the session as "timeout"
- **AND** the system SHALL notify the user via Feishu message

### Requirement: System tracks session execution status
The system SHALL track and report the real-time status of OpenCode session execution.

#### Scenario: Status tracking via SSE
- **WHEN** an OpenCode session is executing
- **THEN** the system SHALL subscribe to SSE events from OpenCode
- **AND** the system SHALL update session status in real-time

#### Scenario: Progress reporting
- **WHEN** session status changes (created → analyzing → executing → completed)
- **THEN** the system SHALL update the Feishu message card with current progress
- **AND** the system SHALL include percentage when available

#### Scenario: Error state capture
- **WHEN** OpenCode reports an error or exception
- **THEN** the system SHALL capture the error message
- **AND** the system SHALL mark session as "error"
- **AND** the system SHALL notify user with error details

### Requirement: System stores and retrieves session history
The system SHALL store session history and allow retrieval of past sessions.

#### Scenario: Session result storage
- **WHEN** a session completes (success or failure)
- **THEN** the system SHALL store the session metadata (id, timestamp, status, summary)
- **AND** the system SHALL store the execution result or error message

#### Scenario: History query
- **WHEN** user sends "/history" command
- **THEN** the system SHALL return a list of recent sessions
- **AND** the system SHALL include session ID, timestamp, status, and brief summary

#### Scenario: Session detail retrieval
- **WHEN** user sends "/session {id}" command
- **THEN** the system SHALL retrieve and display the full session details
- **AND** the system SHALL include all messages exchanged in that session

### Requirement: System manages project context
The system SHALL manage the current project context for each user.

#### Scenario: Project path configuration
- **WHEN** user configures a project path via web UI
- **THEN** the system SHALL validate the path exists and is a git repository
- **AND** the system SHALL store the project configuration

#### Scenario: Context switching
- **WHEN** user switches active project
- **THEN** the system SHALL update the current project context
- **AND** the system SHALL notify the local agent of the change

#### Scenario: Invalid project detection
- **WHEN** local agent reports project path is invalid or inaccessible
- **THEN** the system SHALL mark the project as "unavailable"
- **AND** the system SHALL prompt user to check configuration
