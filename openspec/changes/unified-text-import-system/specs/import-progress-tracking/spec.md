## ADDED Requirements

### Requirement: Four-stage progress tracking
The system SHALL track progress through four distinct stages.

#### Scenario: Stage definition
- **WHEN** import task begins
- **THEN** system SHALL define 4 stages:
  1. Upload (0-20%): File transfer from client
  2. Preprocess (20-40%): Text cleaning and encoding
  3. Parse (40-80%): Chapter detection and AI analysis
  4. Store (80-100%): Database persistence

#### Scenario: Stage progression
- **WHEN** a stage completes
- **THEN** system SHALL emit stage_complete event
- **AND** include: stage_name, duration_seconds, items_processed

#### Scenario: Stage retry
- **WHEN** a stage fails and is retried
- **THEN** progress SHALL revert to stage start percentage
- **AND** progress forward again on retry

### Requirement: WebSocket progress notifications
The system SHALL send real-time progress updates via WebSocket.

#### Scenario: Progress message format
- **WHEN** progress updates
- **THEN** WebSocket message SHALL contain:
  ```json
  {
    "type": "import_progress_update",
    "task_id": 123,
    "stage": "parse",
    "overall_progress": 45,
    "stage_progress": 25,
    "message": "Analyzing chapter structure...",
    "chapters_found": 150,
    "current_chapter": 45,
    "eta_seconds": 120
  }
  ```

#### Scenario: Heartbeat mechanism
- **WHEN** processing takes > 30 seconds
- **THEN** system SHALL send heartbeat every 10 seconds
- **AND** include current stage and progress

#### Scenario: Completion notification
- **WHEN** import completes successfully
- **THEN** system SHALL send import_completed message
- **AND** include: work_id, edition_id, chapter_count, total_chars, processing_time

#### Scenario: Failure notification
- **WHEN** import fails
- **THEN** system SHALL send import_failed message
- **AND** include: error_message, failed_stage, can_retry, error_details

### Requirement: Progress persistence
The system SHALL persist progress to database for recovery.

#### Scenario: Database updates
- **WHEN** progress changes
- **THEN** system SHALL update UnifiedAgentTask.progress field
- **AND** update frequency SHALL be: every 5% OR every 10 seconds

#### Scenario: Resume capability
- **WHEN** server restarts during import
- **THEN** system SHALL resume from last persisted state
- **AND** re-establish WebSocket connections to notify clients

#### Scenario: Progress query API
- **WHEN** client requests GET /api/v1/text/import-task/{task_id}
- **THEN** system SHALL return current progress and status
- **AND** include stage breakdown with timestamps

### Requirement: Frontend progress display
The system SHALL provide visual progress indication in frontend.

#### Scenario: Progress bar component
- **WHEN** import is in progress
- **THEN** frontend SHALL display progress bar with:
  - Overall percentage (0-100%)
  - Current stage name
  - Animated progress indicator
  - Estimated time remaining

#### Scenario: Stage indicators
- **WHEN** viewing import progress
- **THEN** system SHALL show 4 stage indicators:
  - Completed stages: green checkmark
  - Current stage: animated spinner
  - Pending stages: gray circle

#### Scenario: Detail expansion
- **WHEN** user clicks progress bar
- **THEN** system SHALL expand to show:
  - Per-stage progress
  - Chapters processed count
  - Current operation description
  - Any warnings or errors

#### Scenario: Completion view
- **WHEN** import completes
- **THEN** frontend SHALL show success animation
- **AND** display summary: work title, chapter count, processing time
- **AND** provide buttons: "View Work", "Import Another", "Close"
