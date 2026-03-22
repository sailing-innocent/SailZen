## ADDED Requirements

### Requirement: Structured intent plans from conversational input
The system SHALL convert Feishu messages, speech-derived text blocks, and card actions into structured intent plans before any remote execution begins.

#### Scenario: Natural language becomes an executable plan
- **WHEN** the operator sends a request describing a remote development action
- **THEN** the system produces a structured intent plan containing action type, target workspace or session, parameters, confidence, and risk classification

#### Scenario: Card actions bypass ambiguous parsing
- **WHEN** the operator taps a structured action on a Feishu card
- **THEN** the system converts the action payload into the same structured intent plan format without depending on free-form parsing

### Requirement: Template-based normalization draft
The system SHALL normalize messy free-form requests into operator-visible drafts using intent templates before execution is allowed.

#### Scenario: Speech-derived text is cleaned into a draft
- **WHEN** the operator sends a long text block with filler words, duplicated phrases, or likely transcription mistakes
- **THEN** the system maps the request into an intent template and returns a cleaned draft with target, action, parameters, and unresolved fields

#### Scenario: Draft shows unresolved slots
- **WHEN** the normalization process cannot confidently fill one or more template slots
- **THEN** the system marks those slots as unresolved and asks the operator for targeted clarification

### Requirement: Validation and clarification before execution
The system SHALL validate each intent plan against deterministic policies and request clarification when targets, parameters, normalization output, or safety posture are unclear.

#### Scenario: Missing workspace target
- **WHEN** the intent plan does not identify a unique workspace or session
- **THEN** the system asks the operator to choose from valid candidates before execution continues

#### Scenario: High-risk intent requires confirmation
- **WHEN** the intent plan is classified as confirmation-required by policy
- **THEN** the system presents a confirmation step and MUST NOT execute the action until confirmation is received

#### Scenario: Free-form request requires second confirmation
- **WHEN** a free-form text request has been normalized into a draft plan
- **THEN** the system MUST require operator confirmation or edit approval of that normalized draft before execution begins

### Requirement: Degraded routing fallback
The system SHALL provide deterministic routing for a defined set of safe and common actions when the LLM routing layer is unavailable or fails validation.

#### Scenario: LLM provider outage during status request
- **WHEN** the LLM routing layer is unavailable and the operator requests a supported safe action such as status or refresh
- **THEN** the system routes the request through deterministic fallback handling and returns a valid response

#### Scenario: Unrecoverable routing failure
- **WHEN** the request cannot be safely interpreted by either LLM routing or deterministic fallback
- **THEN** the system records the failure and returns a clarification response instead of executing a guessed action

#### Scenario: Draft normalization confidence is too low
- **WHEN** the system cannot normalize a messy text request with sufficient confidence
- **THEN** the system returns a non-executable clarification draft rather than creating an execution plan
