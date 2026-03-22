## ADDED Requirements

### Requirement: Policy-based action authorization
The system SHALL evaluate every remote development action against sender identity, workspace policy, action class, and session state before execution.

#### Scenario: Authorized safe action
- **WHEN** an allowed sender requests a safe action within an authorized workspace
- **THEN** the system permits execution without additional confirmation

#### Scenario: Unauthorized workspace access
- **WHEN** a sender requests an action against a workspace outside the configured authorization policy
- **THEN** the system denies the action and records the attempt in audit history

### Requirement: Confirmation for sensitive operations
The system SHALL require explicit operator confirmation before executing destructive or high-risk actions.

#### Scenario: Git push requested from mobile
- **WHEN** the operator requests a push or comparable high-risk operation
- **THEN** the system shows a confirmation step summarizing the target workspace, action, and risk before executing it

#### Scenario: Confirmation expires
- **WHEN** a pending confirmation is not approved within the configured expiry window
- **THEN** the system cancels the pending action without executing it

### Requirement: Auditable degraded-mode behavior
The system SHALL record when it falls back to degraded handling modes and MUST avoid unsafe execution during degraded operation.

#### Scenario: LLM routing unavailable for high-risk request
- **WHEN** the operator requests a high-risk action while the LLM routing layer is unavailable
- **THEN** the system refuses automatic execution and records that the request was blocked by degraded-mode safety policy

#### Scenario: Feishu delivery fails after action is accepted
- **WHEN** an action is accepted for execution but the response cannot be delivered to Feishu immediately
- **THEN** the system persists the action state and makes the eventual outcome retrievable from later status checks
