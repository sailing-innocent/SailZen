## ADDED Requirements

### Requirement: Exercise type selection
The user SHALL be able to select from predefined exercise types.

#### Scenario: Select exercise type
- **WHEN** the user creates a new exercise record
- **THEN** they see a list of exercise types: 跑步, 游泳, 骑行, 健身, 瑜伽, 其他
- **AND** they can select one type

### Requirement: Exercise duration recording
The user SHALL be able to record exercise duration.

#### Scenario: Record duration
- **WHEN** the user creates an exercise record
- **THEN** they can input duration in minutes
- **AND** a quick-select option for common durations (15, 30, 45, 60 min)

### Requirement: Calories estimation
The app SHALL calculate estimated calories burned based on exercise type and duration.

#### Scenario: Auto-calculate calories
- **WHEN** the user selects exercise type and duration
- **THEN** the app displays estimated calories burned
- **AND** the calculation uses MET values:
  - 跑步: 10 MET
  - 游泳: 8 MET
  - 骑行: 7 MET
  - 健身: 6 MET
  - 瑜伽: 3 MET
  - 其他: 4 MET
- **AND** the user can manually override the value

### Requirement: Exercise history list
The user SHALL be able to view their exercise history.

#### Scenario: View exercise records
- **WHEN** the user navigates to the exercise screen
- **THEN** they see a list of exercise records
- **AND** each record shows type, duration, calories, and date
- **AND** records are grouped by date (今天, 昨天, 本周, 更早)

### Requirement: Exercise statistics
The app SHALL display exercise statistics and summaries.

#### Scenario: View exercise stats
- **WHEN** the user is on the exercise screen
- **THEN** they see summary cards:
  - 本周运动次数
  - 本周总时长
  - 本周消耗卡路里
- **AND** the period can be changed (本周, 本月, 本年)

### Requirement: Edit and delete exercise records
The user SHALL be able to modify or remove exercise records.

#### Scenario: Edit exercise
- **WHEN** the user taps an exercise record
- **THEN** they enter edit mode
- **AND** they can modify any field
- **AND** save changes locally

#### Scenario: Delete exercise
- **WHEN** the user swipes left on an exercise record
- **THEN** a delete option appears
- **WHEN** they confirm deletion
- **THEN** the record is removed locally

