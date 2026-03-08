## ADDED Requirements

### Requirement: Text sanitization
The system SHALL sanitize text to remove problematic characters and sequences.

#### Scenario: NUL character removal
- **WHEN** text contains NUL (\x00) characters
- **THEN** system SHALL remove all NUL characters
- **AND** log count of removed characters

#### Scenario: BOM removal
- **WHEN** text starts with UTF-8 BOM (EF BB BF)
- **THEN** system SHALL strip BOM
- **AND** process remaining text normally

#### Scenario: Whitespace normalization
- **WHEN** text contains mixed line endings (CR, LF, CRLF)
- **THEN** system SHALL normalize to LF (\n)
- **AND** collapse multiple consecutive blank lines to single blank line

#### Scenario: Leading/trailing whitespace
- **WHEN** text lines have leading/trailing whitespace
- **THEN** system SHALL trim each line
- **AND** preserve intentional indentation of dialogue or poetry

### Requirement: Advertisement and noise removal
The system SHALL automatically detect and remove advertisements and noise.

#### Scenario: URL removal
- **WHEN** text contains URLs (http://, https://, www.)
- **THEN** system SHALL remove entire URL lines
- **AND** log removed URLs for review

#### Scenario: Platform watermarks
- **WHEN** text contains platform-specific markers like "起点中文网", "QQ阅读", "Kindle"
- **THEN** system SHALL remove these watermarks
- **AND** preserve surrounding content

#### Scenario: Promotional content
- **WHEN** text contains promotional phrases like "新书推荐", "求月票", "加更通知"
- **THEN** system SHALL flag these sections
- **AND** offer to remove during import

#### Scenario: Symbol-only lines
- **WHEN** text lines contain only symbols (*, #, =, -, etc.) and no Chinese/English characters
- **THEN** system SHALL remove lines with > 5 consecutive symbols
- **AND** keep lines with meaningful symbols (e.g., "***" as scene separator)

### Requirement: Encoding normalization
The system SHALL handle various text encodings and normalize to UTF-8.

#### Scenario: Automatic encoding detection
- **WHEN** file encoding is unknown
- **THEN** system SHALL use chardet library to detect encoding
- **AND** confidence score SHALL be > 0.7 for auto-detection

#### Scenario: Encoding conversion
- **WHEN** file is detected as GBK, GB2312, Big5, or Shift-JIS
- **THEN** system SHALL convert to UTF-8
- **AND** handle conversion errors gracefully (replace with �)

#### Scenario: Mixed encoding handling
- **WHEN** file contains mixed encodings (rare but possible in corrupted files)
- **THEN** system SHALL process line by line
- **AND** skip lines that cannot be decoded

### Requirement: Text statistics calculation
The system SHALL calculate basic statistics for the processed text.

#### Scenario: Character counting
- **WHEN** text preprocessing completes
- **THEN** system SHALL calculate:
  - Total characters (including spaces)
  - Chinese characters only
  - Word count (English words)
  - Line count

#### Scenario: Content analysis
- **WHEN** text is cleaned
- **THEN** system SHALL detect:
  - Primary language (zh/en/ja/mixed)
  - Estimated chapter count (based on length)
  - Average line length
  - Presence of dialogue markers (", ')

#### Scenario: Metadata extraction
- **WHEN** processing begins
- **THEN** system SHALL extract metadata from filename:
  - Remove extension
  - Split author if format is "Title - Author.txt"
  - Detect series patterns (e.g., "Book 1 - Title.txt")
