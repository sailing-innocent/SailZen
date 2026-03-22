## ADDED Requirements

### Requirement: System executes git pull operations
The system SHALL execute git pull operations safely with proper error handling.

#### Scenario: Successful git pull
- **WHEN** user sends "/git-pull" or "/git-pull origin main"
- **THEN** the system SHALL execute git pull in the configured project directory
- **AND** the system SHALL capture the output (success message or up-to-date)
- **AND** the system SHALL report the result to user via Feishu

#### Scenario: Git pull with conflicts
- **WHEN** git pull results in merge conflicts
- **THEN** the system SHALL detect the conflict
- **AND** the system SHALL abort the merge (git merge --abort)
- **AND** the system SHALL notify user about conflicts requiring manual resolution

#### Scenario: Git pull authentication failure
- **WHEN** git pull fails due to authentication issues
- **THEN** the system SHALL capture the error message
- **AND** the system SHALL suggest checking SSH key or credentials

### Requirement: System executes git commit and push operations
The system SHALL execute git commit and push with safety checks.

#### Scenario: Git commit with message
- **WHEN** user sends "/git-commit 'fix: resolve login issue'"
- **THEN** the system SHALL stage all modified files (git add .)
- **AND** the system SHALL create a commit with the provided message
- **AND** the system SHALL report the commit hash and status

#### Scenario: Git commit with confirmation
- **WHEN** user sends "/git-commit" without message
- **THEN** the system SHALL show a list of modified files
- **AND** the system SHALL ask for confirmation and commit message
- **AND** the system SHALL only proceed after user confirmation

#### Scenario: Git push to remote
- **WHEN** user sends "/git-push"
- **THEN** the system SHALL check if local branch is ahead of remote
- **AND** the system SHALL push commits to remote
- **AND** the system SHALL report success or failure

#### Scenario: Protected branch prevention
- **WHEN** user attempts to push to a protected branch (e.g., main/master)
- **THEN** the system SHALL detect branch protection
- **AND** the system SHALL warn user and suggest creating a feature branch
- **AND** the system SHALL NOT execute the push without explicit override

### Requirement: System provides git status and information
The system SHALL provide git status information on demand.

#### Scenario: Git status report
- **WHEN** user sends "/git-status"
- **THEN** the system SHALL execute git status
- **AND** the system SHALL format the output showing:
  - Current branch
  - Modified files
  - Staged files
  - Untracked files
  - Ahead/behind remote info

#### Scenario: Git log summary
- **WHEN** user sends "/git-log [n]"
- **THEN** the system SHALL show the last n commits (default 5)
- **AND** the system SHALL include commit hash, message, author, and date

### Requirement: System manages git safety checks
The system SHALL perform safety checks before executing git operations.

#### Scenario: Uncommitted changes check
- **WHEN** user requests git pull and there are uncommitted changes
- **THEN** the system SHALL warn about potential merge conflicts
- **AND** the system SHALL suggest committing or stashing changes first

#### Scenario: Large file detection
- **WHEN** a commit would include files larger than 10MB
- **THEN** the system SHALL warn about large files
- **AND** the system SHALL suggest using git-lfs or excluding the files

#### Scenario: Sensitive file detection
- **WHEN** a commit would include potential sensitive files (.env, *.key, *.pem)
- **THEN** the system SHALL warn about sensitive files
- **AND** the system SHALL check if they are in .gitignore
- **AND** the system SHALL require explicit confirmation to proceed
