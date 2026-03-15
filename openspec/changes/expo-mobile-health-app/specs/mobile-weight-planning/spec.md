## ADDED Requirements

### Requirement: Create weight goal
The user SHALL be able to set a target weight and deadline.

#### Scenario: Set new goal
- **WHEN** the user navigates to the 目标 tab
- **AND** taps "设置目标"
- **THEN** a form appears with fields:
  - 目标体重 (kg)
  - 目标日期
  - 起始体重 (default: current weight)
- **WHEN** they fill in the form and confirm
- **THEN** the weight plan is saved locally

#### Scenario: Validation
- **WHEN** the user enters invalid values (negative weight, past date)
- **THEN** validation errors are displayed
- **AND** the form cannot be submitted

### Requirement: View current goal
The user SHALL be able to see their active weight goal and progress.

#### Scenario: Display current goal
- **WHEN** the user navigates to the 目标 tab
- **AND** they have an active goal
- **THEN** they see:
  - 目标体重
  - 目标日期
  - 当前体重
  - 还需减重/增重
  - 剩余天数

### Requirement: Progress tracking
The app SHALL calculate and display progress toward the weight goal.

#### Scenario: Calculate progress
- **WHEN** the user views their goal
- **THEN** they see progress as a percentage
- **AND** they see a progress bar visualization
- **AND** they see the expected weight for today based on linear interpolation

#### Scenario: Progress chart
- **WHEN** the user is on the goal screen
- **THEN** they see a chart showing:
  - Goal line (linear path from start to target)
  - Actual weight data points
  - Highlighted deviation from goal

### Requirement: Goal status indicators
The app SHALL provide visual feedback on goal status.

#### Scenario: On track indication
- **WHEN** the user's current weight is within ±0.5kg of expected weight
- **THEN** the status shows "正常" with green indicator

#### Scenario: Behind schedule
- **WHEN** the user's weight is more than 0.5kg above expected (for weight loss)
- **THEN** the status shows "落后" with red indicator

#### Scenario: Ahead of schedule
- **WHEN** the user's weight is more than 0.5kg below expected (for weight loss)
- **THEN** the status shows "超前" with blue indicator

### Requirement: Goal history
The user SHALL be able to view completed or past goals.

#### Scenario: View goal history
- **WHEN** the user taps "历史目标"
- **THEN** they see a list of past goals
- **AND** each goal shows final result and whether it was achieved

