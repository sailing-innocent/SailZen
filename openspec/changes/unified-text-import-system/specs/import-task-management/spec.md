## ADDED Requirements

### Requirement: Import task list API
The system SHALL provide API to list and query import tasks.

#### Scenario: List all tasks
- **WHEN** client sends GET /api/v1/text/import-tasks
- **THEN** system SHALL return paginated list of import tasks
- **AND** default sort SHALL be created_at DESC

#### Scenario: Filter by status
- **WHEN** client sends GET /api/v1/text/import-tasks?status=running
- **THEN** system SHALL return only tasks with matching status
- **AND** support multiple statuses: pending, running, completed, failed, cancelled

#### Scenario: Filter by date range
- **WHEN** client sends GET /api/v1/text/import-tasks?start_date=2024-01-01&end_date=2024-01-31
- **THEN** system SHALL return tasks created within date range

#### Scenario: Search by work title
- **WHEN** client sends GET /api/v1/text/import-tasks?search=关键词
- **THEN** system SHALL return tasks where work_title contains search term
- **AND** search SHALL be case-insensitive

### Requirement: Task detail view
The system SHALL provide detailed information about individual import tasks.

#### Scenario: Task detail API
- **WHEN** client sends GET /api/v1/text/import-task/{task_id}
- **THEN** system SHALL return complete task information:
  ```json
  {
    "id": 123,
    "task_type": "text_import",
    "status": "completed",
    "work_title": "Example Book",
    "work_author": "Author Name",
    "priority": 5,
    "progress": 100,
    "created_at": "2024-01-15T10:30:00Z",
    "started_at": "2024-01-15T10:30:05Z",
    "completed_at": "2024-01-15T10:35:20Z",
    "processing_time_seconds": 315,
    "result": {
      "work_id": 456,
      "edition_id": 789,
      "chapter_count": 200,
      "total_chars": 1500000,
      "warnings": [
        {
          "type": "oversized_chapter",
          "chapter_index": 150,
          "message": "Chapter 150 is unusually long"
        }
      ]
    },
    "stages": [
      {
        "name": "upload",
        "status": "completed",
        "progress": 100,
        "started_at": "...",
        "completed_at": "..."
      }
    ]
  }
  ```

#### Scenario: Task not found
- **WHEN** client requests non-existent task_id
- **THEN** system SHALL return 404 with message "Task not found"

### Requirement: Task lifecycle operations
The system SHALL support operations to manage import task lifecycle.

#### Scenario: Cancel task
- **WHEN** client sends POST /api/v1/text/import-task/{task_id}/cancel
- **AND** task is in pending or running state
- **THEN** system SHALL mark task as cancelled
- **AND** stop processing at next checkpoint
- **AND** return 200 with success message

#### Scenario: Cancel completed task
- **WHEN** client tries to cancel already completed task
- **THEN** system SHALL return 400 with error "Task already completed"

#### Scenario: Retry failed task
- **WHEN** client sends POST /api/v1/text/import-task/{task_id}/retry
- **AND** task is in failed state
- **THEN** system SHALL reset task to pending
- **AND** preserve previous configuration
- **AND** return new task_id (or same if reusing)

#### Scenario: Delete task record
- **WHEN** client sends DELETE /api/v1/text/import-task/{task_id}
- **THEN** system SHALL delete task record from database
- **AND** associated data (Work, Edition) SHALL remain intact
- **AND** temporary files SHALL be cleaned up

### Requirement: Frontend task management UI
The system SHALL provide user interface for managing import tasks.

#### Scenario: Task list view
- **WHEN** user navigates to Import Tasks page
- **THEN** system SHALL display table with columns:
  - Work Title (clickable link)
  - Status (with color-coded badge)
  - Progress (progress bar)
  - Created At
  - Actions (View, Cancel, Retry, Delete)

#### Scenario: Task filtering
- **WHEN** user views task list
- **THEN** system SHALL provide filters:
  - Status dropdown (All, Pending, Running, Completed, Failed, Cancelled)
  - Date range picker
  - Search box for work title

#### Scenario: Real-time updates
- **WHEN** viewing task list
- **AND** a task's status or progress changes
- **THEN** system SHALL update row in real-time via WebSocket
- **AND** highlight recently changed rows

#### Scenario: Bulk operations
- **WHEN** user selects multiple tasks
- **THEN** system SHALL show bulk action buttons:
  - "Retry Selected" (for failed tasks)
  - "Cancel Selected" (for pending/running tasks)
  - "Delete Selected"

### Requirement: Task retention and cleanup
The system SHALL manage task history with retention policies.

#### Scenario: Automatic cleanup
- **WHEN** task is completed or failed
- **AND** 30 days have passed
- **THEN** system SHALL automatically delete task record
- **AND** preserve imported Work and Edition data

#### Scenario: Manual cleanup
- **WHEN** user requests cleanup of old tasks
- **THEN** system SHALL provide "Cleanup Old Tasks" button
- **AND** delete all completed/failed/cancelled tasks older than 30 days

#### Scenario: Retention configuration
- **WHEN** admin configures retention_days setting
- **THEN** system SHALL use configured value instead of default 30
- **AND** minimum SHALL be 7 days, maximum 365 days
