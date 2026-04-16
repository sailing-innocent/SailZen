## ADDED Requirements

### Requirement: Async import task creation
The system SHALL provide an API endpoint to create asynchronous text import tasks.

#### Scenario: Create import task
- **WHEN** client sends POST /api/v1/text/import-async with: file_id, work_title, work_author, enable_ai_parsing
- **THEN** system SHALL create UnifiedAgentTask with task_type="text_import"
- **AND** return task_id immediately (within 500ms)
- **AND** task SHALL be queued for execution

#### Scenario: Task payload structure
- **WHEN** import task is created
- **THEN** payload SHALL contain:
  - file_path: temporary file location
  - work_title: book title
  - work_author: author name (optional)
  - enable_ai_parsing: boolean flag
  - detected_encoding: file encoding
  - client_id: for WebSocket notifications

#### Scenario: Duplicate detection
- **WHEN** creating import task for file with same checksum as existing work
- **THEN** system SHALL warn user "Similar work already exists"
- **AND** ask for confirmation before proceeding

### Requirement: Task scheduling and execution
The system SHALL integrate text import with UnifiedAgentScheduler.

#### Scenario: Queue management
- **WHEN** import task is created
- **THEN** system SHALL add task to scheduler queue with priority=5 (NORMAL)
- **AND** task SHALL wait if max concurrent imports (2) reached

#### Scenario: Concurrent limit
- **WHEN** 2 import tasks are already running
- **AND** new import task is submitted
- **THEN** new task SHALL be queued
- **AND** client SHALL receive "queued" status with position number

#### Scenario: Task execution
- **WHEN** task reaches front of queue
- **THEN** system SHALL mark task as "running"
- **AND** begin processing through 4 stages: upload(complete), preprocess, parse, store
- **AND** update progress after each stage completion

#### Scenario: Task priority
- **WHEN** creating import task with priority parameter
- **THEN** priority SHALL be: 1=CRITICAL, 3=HIGH, 5=NORMAL, 7=LOW, 10=BACKGROUND
- **AND** default SHALL be 5 (NORMAL)

### Requirement: Task lifecycle management
The system SHALL manage import task states throughout processing.

#### Scenario: State transitions
- **WHEN** task is created
- **THEN** state SHALL progress: pending → scheduled → running → [completed|failed]
- **AND** each state change SHALL be persisted to database
- **AND** WebSocket notification SHALL be sent on each transition

#### Scenario: Task cancellation
- **WHEN** user requests to cancel running import task
- **THEN** system SHALL stop processing at next checkpoint
- **AND** mark task as "cancelled"
- **AND** cleanup temporary resources

#### Scenario: Task retry
- **WHEN** import task fails at storage stage
- **THEN** user SHALL be able to retry from failed stage
- **AND** previous parsing results SHALL be reused if applicable

### Requirement: Result persistence
The system SHALL persist import results to database.

#### Scenario: Successful import
- **WHEN** import completes successfully
- **THEN** system SHALL create Work record
- **AND** create Edition record linked to Work
- **AND** create DocumentNode records for each chapter
- **AND** task result SHALL contain: work_id, edition_id, chapter_count, total_chars

#### Scenario: Partial success with warnings
- **WHEN** import completes with warnings (e.g., some chapters too long)
- **THEN** data SHALL still be saved
- **AND** warnings SHALL be stored in task.result.warnings array
- **AND** user SHALL be notified of issues

#### Scenario: Complete failure
- **WHEN** import fails before any data saved
- **THEN** no database records SHALL be created
- **AND** error SHALL be logged
- **AND** temporary file SHALL be retained for debugging
