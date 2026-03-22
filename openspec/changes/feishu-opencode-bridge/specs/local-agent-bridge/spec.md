## ADDED Requirements

### Requirement: Local agent connects to cloud gateway
The local agent SHALL establish and maintain a connection to the cloud gateway.

#### Scenario: Successful connection with PIN
- **WHEN** local agent starts with valid configuration (cloud URL, PIN)
- **THEN** the agent SHALL connect via WebSocket to cloud gateway
- **AND** the agent SHALL authenticate with 6-digit PIN
- **THEN** the cloud SHALL return JWT token for subsequent requests
- **AND** the agent SHALL mark connection status as "connected"

#### Scenario: Authentication failure
- **WHEN** local agent provides invalid PIN
- **THEN** the cloud SHALL reject the connection with 401 Unauthorized
- **AND** the agent SHALL retry with exponential backoff (max 3 attempts)
- **AND** after 3 failures, the agent SHALL exit with error message

#### Scenario: Connection loss and reconnection
- **WHEN** WebSocket connection drops unexpectedly
- **THEN** the agent SHALL detect disconnection within 15 seconds
- **AND** the agent SHALL attempt reconnection with exponential backoff
- **AND** the agent SHALL resume pending tasks after successful reconnection

### Requirement: Local agent manages OpenCode lifecycle
The local agent SHALL manage OpenCode server lifecycle and health.

#### Scenario: OpenCode auto-start
- **WHEN** agent connects to cloud and no OpenCode instance is running
- **THEN** the agent SHALL start OpenCode server on configured port
- **AND** the agent SHALL wait for OpenCode health check to pass
- **AND** the agent SHALL report OpenCode status as "ready"

#### Scenario: OpenCode health monitoring
- **WHEN** OpenCode is running
- **THEN** the agent SHALL check health endpoint every 30 seconds
- **AND** the agent SHALL report health status to cloud
- **AND** if unhealthy for 2 consecutive checks, the agent SHALL restart OpenCode

#### Scenario: OpenCode remote start via desired state
- **WHEN** cloud updates desired_state to "opencode_running: true"
- **AND** the agent detects actual state is "stopped"
- **THEN** the agent SHALL start OpenCode server on configured port and project path
- **AND** the agent SHALL wait for health check to pass
- **AND** the agent SHALL report actual state as "running" to cloud

#### Scenario: OpenCode remote stop via desired state
- **WHEN** cloud updates desired_state to "opencode_running: false"
- **AND** the agent detects actual state is "running"
- **THEN** the agent SHALL gracefully stop OpenCode process
- **AND** the agent SHALL wait for process termination
- **AND** the agent SHALL report actual state as "stopped" to cloud

#### Scenario: Automatic recovery after crash
- **WHEN** OpenCode process crashes unexpectedly
- **AND** desired_state indicates "opencode_running: true"
- **THEN** the agent SHALL detect the crash within 15 seconds
- **AND** the agent SHALL automatically restart OpenCode
- **AND** the agent SHALL notify cloud about the recovery
- **AND** if restart fails 3 times, the agent SHALL mark state as "error" and notify user

#### Scenario: Project path switching
- **WHEN** cloud updates desired_state with new "project_path"
- **THEN** the agent SHALL verify new path exists and is git repository
- **AND** the agent SHALL update OpenCode working directory
- **AND** if OpenCode is running, the agent SHALL restart it with new path
- **AND** the agent SHALL report new project context to cloud

### Requirement: Local agent monitors and reconciles desired state
The local agent SHALL continuously monitor desired state from cloud and reconcile with actual state.

#### Scenario: State reconciliation loop
- **WHEN** the agent is running
- **THEN** the agent SHALL check desired_state from cloud every 5 seconds
- **AND** the agent SHALL compare with actual local state
- **AND** if discrepancy detected, the agent SHALL execute corrective action
- **AND** the agent SHALL report reconciliation result to cloud

#### Scenario: Manual override from mobile
- **WHEN** user sends "/start-opencode /work/myproject" from Feishu mobile
- **THEN** cloud SHALL update desired_state with new configuration
- **AND** the agent SHALL receive the update via WebSocket push or polling
- **AND** the agent SHALL execute start operation within 10 seconds
- **AND** the agent SHALL report progress (starting → running) via Feishu message

### Requirement: Local agent executes commands from cloud
The local agent SHALL receive and execute commands forwarded from cloud gateway.

#### Scenario: Git command execution
- **WHEN** cloud sends "git-pull" command
- **THEN** the agent SHALL execute git pull in project directory
- **AND** the agent SHALL capture stdout and stderr
- **AND** the agent SHALL return exit code and output to cloud

#### Scenario: OpenCode session command
- **WHEN** cloud sends OpenCode session request
- **THEN** the agent SHALL create new OpenCode session via HTTP API
- **AND** the agent SHALL subscribe to SSE events
- **AND** the agent SHALL forward events to cloud in real-time

#### Scenario: File content request
- **WHEN** cloud requests file content for diff display
- **THEN** the agent SHALL read file from project directory
- **AND** the agent SHALL return file content (truncated if >100KB)
- **AND** the agent SHALL handle binary files appropriately

### Requirement: Local agent provides system information
The local agent SHALL provide local system information to cloud.

#### Scenario: System status report
- **WHEN** cloud requests system status
- **THEN** the agent SHALL report:
  - Connection status (connected/disconnected)
  - OpenCode status (running/stopped/error)
  - Current project path
  - Git repository status (branch, clean/dirty)
  - System resources (optional: CPU, memory usage)

#### Scenario: Project list discovery
- **WHEN** cloud requests available projects
- **THEN** the agent SHALL scan configured parent directories
- **AND** the agent SHALL return list of git repositories found
- **AND** for each project, include name, path, and current branch

### Requirement: Local agent handles file operations
The local agent SHALL perform file operations requested by cloud.

#### Scenario: File read
- **WHEN** cloud requests to read specific file
- **THEN** the agent SHALL verify file is within project directory (security)
- **AND** the agent SHALL read and return file content
- **AND** if file doesn't exist, return appropriate error

#### Scenario: Directory listing
- **WHEN** cloud requests directory contents
- **THEN** the agent SHALL list files and subdirectories
- **AND** the agent SHALL include file sizes and modification times
- **AND** the agent SHALL respect .gitignore for cleaner output

#### Scenario: Diff generation
- **WHEN** cloud requests git diff
- **THEN** the agent SHALL execute git diff
- **AND** the agent SHALL format output for display in Feishu
- **AND** the agent SHALL handle large diffs by truncation
