## Requirements

### Requirement: Challenge state synchronization after check-in
The system SHALL ensure that challenge statistics and progress indicators are updated immediately after any check-in operation (success, failure, or reset) completes.

#### Scenario: Successful check-in updates progress bar
- **WHEN** user successfully checks in to a challenge
- **THEN** the progress bar in the challenge list SHALL update immediately to reflect the new progress
- **AND** the user SHALL NOT need to manually refresh the page

#### Scenario: Failed check-in updates progress bar
- **WHEN** user marks a check-in as failed
- **THEN** the progress bar in the challenge list SHALL update immediately to reflect the failed status
- **AND** the challenge stats SHALL be recalculated and displayed

#### Scenario: Reset check-in updates progress bar
- **WHEN** user resets a previous check-in
- **THEN** the progress bar in the challenge list SHALL update immediately to reflect the reset status
- **AND** the previous progress contribution SHALL be removed from the display

#### Scenario: Multiple check-ins in sequence
- **WHEN** user performs multiple check-ins in rapid succession
- **THEN** each progress bar update SHALL reflect the correct final state
- **AND** race conditions SHALL be prevented to ensure data consistency
