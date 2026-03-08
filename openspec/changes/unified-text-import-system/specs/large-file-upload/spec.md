## ADDED Requirements

### Requirement: Stream-based file upload
The system SHALL support stream-based file upload for text files up to 500MB.

#### Scenario: Upload small file (< 10MB)
- **WHEN** user selects a text file smaller than 10MB
- **THEN** system SHALL upload the file in a single HTTP POST request
- **AND** return upload progress events every 100ms

#### Scenario: Upload large file (10MB - 500MB)
- **WHEN** user selects a text file between 10MB and 500MB
- **THEN** system SHALL use Fetch API ReadableStream to upload
- **AND** display upload progress percentage
- **AND** complete upload within 30 minutes timeout

#### Scenario: File size validation
- **WHEN** user selects a file larger than 500MB
- **THEN** system SHALL reject the file with error "File too large (max 500MB)"
- **AND** prevent upload from starting

#### Scenario: File type validation
- **WHEN** user selects a non-text file (e.g., .exe, .zip)
- **THEN** system SHALL reject with error "Invalid file type"
- **AND** only allow extensions: .txt, .md, .text

### Requirement: Upload progress tracking
The system SHALL provide real-time upload progress to the frontend.

#### Scenario: Progress events
- **WHEN** file upload begins
- **THEN** system SHALL emit progress events at least every 500ms
- **AND** each event SHALL contain: bytesUploaded, totalBytes, percentage

#### Scenario: Upload completion
- **WHEN** upload reaches 100%
- **THEN** system SHALL emit upload_complete event
- **AND** include server-side file identifier for subsequent processing

#### Scenario: Upload failure
- **WHEN** network error occurs during upload
- **THEN** system SHALL emit upload_failed event
- **AND** include error message and allow retry

### Requirement: Temporary file storage
The system SHALL store uploaded files temporarily until processing completes.

#### Scenario: Temporary storage location
- **WHEN** file upload completes
- **THEN** system SHALL save file to temporary directory: /tmp/sailzen_uploads/
- **AND** filename SHALL be: {uuid}_{original_filename}

#### Scenario: Cleanup after success
- **WHEN** import task completes successfully
- **THEN** system SHALL delete temporary file within 5 minutes

#### Scenario: Cleanup after failure
- **WHEN** import task fails or is cancelled
- **THEN** system SHALL retain temporary file for 24 hours for debugging
- **AND** delete automatically after 24 hours

### Requirement: Encoding detection
The system SHALL automatically detect text file encoding.

#### Scenario: UTF-8 file
- **WHEN** user uploads a UTF-8 encoded file
- **THEN** system SHALL correctly detect UTF-8 encoding
- **AND** process without character corruption

#### Scenario: GBK/GB2312 file
- **WHEN** user uploads a GBK or GB2312 encoded Chinese text file
- **THEN** system SHALL detect the encoding
- **AND** convert to UTF-8 for internal processing

#### Scenario: Manual encoding override
- **WHEN** user specifies encoding in upload request
- **THEN** system SHALL use specified encoding instead of auto-detection
- **AND** emit warning if encoding appears incorrect
