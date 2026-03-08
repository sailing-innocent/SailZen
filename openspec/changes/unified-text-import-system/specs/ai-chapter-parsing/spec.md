## ADDED Requirements

### Requirement: AI-powered chapter detection
The system SHALL use LLM to intelligently detect chapter structures in text.

#### Scenario: Standard chapter format
- **WHEN** text contains chapters like "第一章", "Chapter 1", "第1章"
- **AND** enable_ai_parsing is true
- **THEN** AI SHALL identify the chapter pattern
- **AND** generate appropriate regex for parsing

#### Scenario: Non-standard chapter format
- **WHEN** text uses non-standard formats like "【卷一】", "第一回", "Episode 1"
- **THEN** AI SHALL recognize these as chapter markers
- **AND** suggest appropriate parsing strategy

#### Scenario: Multi-level structure
- **WHEN** text has hierarchical structure (Volume → Chapter → Section)
- **THEN** AI SHALL identify all levels
- **AND** generate parsing rules for tree structure

### Requirement: Special chapter recognition
The system SHALL recognize special chapter types beyond standard numbered chapters.

#### Scenario: Prologue chapters
- **WHEN** text contains "楔子", "序章", "前言", "Prologue", "Introduction"
- **THEN** system SHALL classify as prologue type
- **AND** assign sort_index before first regular chapter

#### Scenario: Epilogue chapters
- **WHEN** text contains "尾声", "后记", "Epilogue", "Afterword"
- **THEN** system SHALL classify as epilogue type
- **AND** assign sort_index after last regular chapter

#### Scenario: Interlude chapters
- **WHEN** text contains "间章", "插曲", "Interlude"
- **THEN** system SHALL classify as interlude type
- **AND** maintain position relative to surrounding chapters

#### Scenario: Side story chapters
- **WHEN** text contains "番外", "外传", "Side Story", "Bonus"
- **THEN** system SHALL classify as side_story type
- **AND** mark with special flag in metadata

### Requirement: Sampling-based analysis
The system SHALL analyze text samples to learn chapter patterns.

#### Scenario: Sample selection
- **WHEN** text length > 10000 characters
- **THEN** system SHALL extract 3 samples:
  - Beginning: first 3000 characters
  - Middle: characters around 40-50% of text
  - End: last 3000 characters

#### Scenario: Pattern learning
- **WHEN** samples are extracted
- **THEN** LLM SHALL analyze samples for:
  - Chapter title patterns
  - Section delimiters
  - Common formatting
  - Special markers

#### Scenario: Pattern application
- **WHEN** LLM returns analysis result
- **THEN** system SHALL apply identified patterns to entire text
- **AND** parse chapters accordingly

### Requirement: Chapter quality validation
The system SHALL validate parsed chapters for quality issues.

#### Scenario: Oversized chapter detection
- **WHEN** a chapter exceeds mean + 3 standard deviations in length
- **THEN** system SHALL flag as "possibly_multiple_chapters"
- **AND** suggest re-parsing with stricter rules

#### Scenario: Undersized chapter detection
- **WHEN** a chapter is shorter than mean - 3 standard deviations OR < 100 characters
- **THEN** system SHALL flag as "possibly_noise_or_ad"
- **AND** include in warnings list

#### Scenario: Chapter count validation
- **WHEN** parsed chapter count < 1 OR > 10000
- **THEN** system SHALL flag as suspicious
- **AND** require manual review

#### Scenario: Title extraction
- **WHEN** chapter title contains both label and content (e.g., "第一章 风云初起")
- **THEN** system SHALL split into: label="第一章", title="风云初起"
- **AND** store separately in DocumentNode
