## ADDED Requirements

### Requirement: Local SQLite storage
The app SHALL use SQLite for local data persistence.

#### Scenario: Database initialization
- **WHEN** the app launches for the first time
- **THEN** SQLite database is initialized with tables:
  - weights (id, value, record_time, sync_status, server_id)
  - exercises (id, type, duration, calories, record_time, sync_status, server_id)
  - weight_plans (id, target_weight, target_date, start_weight, start_date, sync_status, server_id)
  - sync_metadata (last_sync_time, pending_count)

### Requirement: Offline data creation
The app SHALL support creating records while offline.

#### Scenario: Create weight offline
- **WHEN** the device has no network connection
- **AND** the user creates a weight record
- **THEN** the record is saved to SQLite with sync_status='pending'
- **AND** the user sees a "离线模式" indicator

#### Scenario: Create exercise offline
- **WHEN** the device is offline
- **AND** the user creates an exercise record
- **THEN** the record is saved locally with pending status
- **AND** it appears in the local list immediately

### Requirement: Manual sync trigger
The user SHALL be able to manually trigger data synchronization.

#### Scenario: Sync button
- **WHEN** the user taps the sync button (in header or settings)
- **THEN** the app uploads all pending records to the server
- **AND** downloads new records from the server
- **AND** shows sync progress and result

#### Scenario: Sync indicator
- **WHEN** there are pending records to sync
- **THEN** a badge shows the pending count
- **AND** the sync button is highlighted

### Requirement: Automatic sync on connection
The app SHALL automatically sync when connection is restored.

#### Scenario: Auto-sync on reconnect
- **WHEN** the device regains network connection
- **AND** there are pending records
- **THEN** the app automatically triggers sync
- **AND** shows a brief notification

### Requirement: Conflict resolution
The system SHALL handle conflicts during sync using last-write-wins strategy.

#### Scenario: Server wins conflict
- **WHEN** a local record conflicts with a server record
- **AND** the server record has a later updated_at timestamp
- **THEN** the server version replaces the local version
- **AND** the user is notified of the update

#### Scenario: Client wins conflict
- **WHEN** syncing a pending record
- **AND** the server accepts the record
- **THEN** the local record is updated with server_id
- **AND** sync_status is changed to 'synced'

### Requirement: Sync error handling
The app SHALL handle sync failures gracefully.

#### Scenario: Network error during sync
- **WHEN** sync is triggered but network fails
- **THEN** records remain in pending state
- **AND** an error message is shown
- **AND** the user can retry later

#### Scenario: Server error handling
- **WHEN** the server returns an error (4xx/5xx)
- **THEN** sync stops for that record
- **AND** other records continue syncing
- **AND** error details are logged

### Requirement: Last sync tracking
The app SHALL track when the last successful sync occurred.

#### Scenario: Display last sync time
- **WHEN** the user opens the app
- **THEN** they can see the last successful sync time
- **AND** if sync is stale (>24 hours), a reminder is shown

