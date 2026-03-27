## 1. Feishu Card Rendering System

### 1.1 Card Template Framework
- [x] 1.1.1 Create `CardRenderer` class with base template system
- [x] 1.1.2 Implement workspace selection card template
- [x] 1.1.3 Implement session status card template with state indicators
- [x] 1.1.4 Implement progress/loading card template
- [x] 1.1.5 Implement confirmation dialog card template
- [x] 1.1.6 Implement result/error card templates

### 1.2 Card Update Mechanism
- [x] 1.2.1 Add `update_card()` method to reply to existing messages
- [x] 1.2.2 Track message_id to card type mapping
- [x] 1.2.3 Implement progress update logic (percentage + animation)
- [x] 1.2.4 Add card color theming (green=success, red=error, blue=info)

### 1.3 Fallback and Error Handling
- [x] 1.3.1 Implement text fallback when card API fails
- [x] 1.3.2 Add card rendering error logging
- [x] 1.3.3 Ensure mobile-responsive card layouts

## 2. Session Lifecycle Binding

### 2.1 State Machine Implementation
- [x] 2.1.1 Define `SessionState` enum: idle, starting, running, stopping, error
- [x] 2.1.2 Implement state transition validation
- [x] 2.1.3 Add state change persistence to disk
- [x] 2.1.4 Implement state change event hooks

### 2.2 Bot Lifecycle Integration
- [x] 2.2.1 Add `on_bot_startup()` to restore sessions from disk
- [x] 2.2.2 Add `on_bot_shutdown()` to gracefully stop sessions
- [x] 2.2.3 Implement stale session detection and cleanup
- [x] 2.2.4 Add crash recovery logic for unclean shutdowns

### 2.3 Health Monitoring
- [x] 2.3.1 Implement periodic health check for running sessions
- [x] 2.3.2 Add auto-recovery for failed sessions (if enabled)
- [x] 2.3.3 Send error notification cards when sessions fail
- [x] 2.3.4 Track health check history

## 3. Progress Feedback System

### 3.1 Operation Progress Indicators
- [x] 3.1.1 Detect operations taking >1 second
- [x] 3.1.2 Send "处理中" card immediately for long operations
- [x] 3.1.3 Support determinate progress (percentage)
- [x] 3.1.4 Support indeterminate progress (spinner)
- [x] 3.1.5 Update cards on completion/failure

### 3.2 Waiting State Management
- [x] 3.2.1 Queue or reject commands during active operations
- [x] 3.2.2 Show "当前有操作进行中" message with wait time
- [x] 3.2.3 Implement operation timeout handling (30s warning)

### 3.3 Real-time Status Updates
- [x] 3.3.1 Subscribe to session state changes
- [x] 3.3.2 Update status cards within 2 seconds of state change
- [x] 3.3.3 Add activity log display (last 5 activities)

## 4. Confirmation Flow System

### 4.1 Risk Level Classification
- [x] 4.1.1 Implement `RiskLevel` enum: safe, guarded, confirm_required
- [x] 4.1.2 Classify all existing commands by risk level
- [x] 4.1.3 Add risk level metadata to action plans

### 4.2 Confirmation Dialog Implementation
- [x] 4.2.1 Create confirmation card with action details
- [x] 4.2.2 Add "确认" / "取消" button handlers
- [x] 4.2.3 Implement 5-minute confirmation timeout
- [x] 4.2.4 Handle text-based confirmation ("确认"/"取消")

### 4.3 Guarded Actions
- [x] 4.3.1 Check resource availability before guarded actions
- [x] 4.3.2 Show warning when resources constrained
- [x] 4.3.3 Allow proceed/cancel choice

### 4.4 Undo Capability (Optional)
- [x] 4.4.1 Add undo window (10 seconds) for stop operations
- [x] 4.4.2 Show "撤销" button in result card
- [x] 4.4.3 Implement session restart for undo

## 5. Integration and Refactoring

### 5.1 Refactor Message Handling
- [x] 5.1.1 Replace text replies with card replies where appropriate
- [x] 5.1.2 Update `_execute_plan()` to return card messages
- [x] 5.1.3 Maintain backward compatibility for core commands

### 5.2 State Persistence
- [x] 5.2.1 Create `~/.config/feishu-agent/session_states.json`
- [x] 5.2.2 Save session states on every state change
- [x] 5.2.3 Load and validate states on bot startup

### 5.3 Error Handling Improvements
- [x] 5.3.1 Show user-friendly error cards instead of stack traces
- [x] 5.3.2 Add retry options to error cards where applicable
- [x] 5.3.3 Implement graceful degradation on API failures

## 6. Testing and Validation

### 6.1 Unit Tests
- [x] 6.1.1 Test card rendering for all templates
- [x] 6.1.2 Test state machine transitions
- [x] 6.1.3 Test risk level classification
- [x] 6.1.4 Test confirmation flow timeouts

### 6.2 Integration Tests
- [x] 6.2.1 Test end-to-end: start → progress → running → status card
- [x] 6.2.2 Test bot restart with active sessions
- [x] 6.2.3 Test confirmation flow in Feishu
- [x] 6.2.4 Test error recovery and card updates

### 6.3 Manual Testing
- [x] 6.3.1 Test on Feishu mobile app
- [x] 6.3.2 Verify card layouts on different screen sizes
- [x] 6.3.3 Test all command scenarios with cards
