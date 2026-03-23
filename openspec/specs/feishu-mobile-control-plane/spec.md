## ADDED Requirements

### Requirement: Mobile-first remote control interactions
The system SHALL provide a Feishu-native mobile control plane for remote development that supports free-form text, voice-input-method text, and tap-first actions without requiring slash commands for core workflows.

#### Scenario: User starts from a mobile-friendly entry point
- **WHEN** the operator opens the Feishu conversation or invokes the bot menu
- **THEN** the system returns a workspace home view with quick actions for recent projects, active sessions, and common remote development tasks

#### Scenario: User sends a natural-language request without slash syntax
- **WHEN** the operator sends a free-form message such as “打开 SailZen 的开发会话并看下当前状态”
- **THEN** the system accepts the request without requiring the user to reformat it as a slash command

#### Scenario: User sends a long messy voice-input text block
- **WHEN** the operator sends a long text block produced by a speech-to-text keyboard or input method with filler words or recognition mistakes
- **THEN** the system accepts it as a valid input form and routes it into normalization rather than rejecting it for format errors

### Requirement: Rich card responses for remote development state
The system SHALL render status, task progress, and action affordances as Feishu cards rather than plain text for core remote development workflows.

#### Scenario: User requests session status
- **WHEN** the operator asks for the status of a workspace or session
- **THEN** the system returns a card showing workspace name, session status, branch, latest activity, health summary, and actionable controls

#### Scenario: Long-running work produces progress updates
- **WHEN** a remote development task continues after the initial response
- **THEN** the system updates or reissues a card with progress, current step, latest summary, and follow-up actions

### Requirement: Voice-friendly text normalization
The system SHALL support voice-friendly interaction by accepting large text blocks produced by third-party speech-to-text tools, cleaning them into structured drafts, and presenting them for operator confirmation before execution.

#### Scenario: Messy speech-derived text is normalized
- **WHEN** the operator sends a text request with duplicated phrases, filler words, or likely recognition errors
- **THEN** the system returns a cleaned draft that summarizes the intended action, targets, and key parameters in a more structured form

#### Scenario: Operator performs second confirmation
- **WHEN** the system returns a normalized draft for a speech-derived or otherwise messy request
- **THEN** the operator can confirm, edit, or reject the draft before any execution begins

#### Scenario: Normalization retains uncertainty markers
- **WHEN** the system cannot confidently resolve parts of a speech-derived text request
- **THEN** the returned draft highlights uncertain fields or asks for targeted clarification instead of silently guessing
