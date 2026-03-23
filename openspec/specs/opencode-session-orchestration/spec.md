## ADDED Requirements

### Requirement: Durable multi-session registry
The system SHALL maintain a persistent registry of remote workspaces, desktop agents, and OpenCode sessions so that multiple sessions can be monitored and controlled concurrently.

#### Scenario: Multiple active workspaces exist
- **WHEN** the operator has more than one OpenCode session active across configured workspaces
- **THEN** the system lists each session with its workspace, status, owning desktop agent, and latest heartbeat

#### Scenario: Service restarts during active work
- **WHEN** the backend service restarts while sessions are still running on the desktop
- **THEN** the system restores session visibility from persisted state and reconciles observed state from the desktop agent

### Requirement: Desired-state lifecycle management
The system SHALL manage OpenCode start, stop, restart, and recovery through desired-state reconciliation with a desktop-local execution agent.

#### Scenario: Operator starts a workspace session
- **WHEN** the operator requests that a workspace be started
- **THEN** the system records the desired running state and the desktop agent reconciles the machine to that state

#### Scenario: Session crashes unexpectedly
- **WHEN** the observed OpenCode process exits unexpectedly while desired state remains running
- **THEN** the system marks the session unhealthy, records the failure, and initiates configured recovery or operator escalation behavior

### Requirement: Session-scoped task attachment
The system SHALL associate remote development tasks with a target OpenCode session so progress, results, and failures are visible in session context.

#### Scenario: Work request targets an existing session
- **WHEN** the operator asks the system to continue work within a running session
- **THEN** the created task is linked to that session and its progress is visible from the session cockpit

#### Scenario: Work request targets no running session
- **WHEN** the operator requests work for a workspace that has no active session
- **THEN** the system either creates or requests creation of a session before dispatching session-bound work
