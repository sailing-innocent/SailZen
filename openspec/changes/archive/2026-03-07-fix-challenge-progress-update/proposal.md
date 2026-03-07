## Why

The Challenge page (打卡挑战) has a bug where the progress bar in the challenge list doesn't update in real-time after a successful check-in. Users must manually refresh the page to see updated progress, creating a confusing user experience.

## What Changes

- Fix the state synchronization issue between the global store and local component state after check-in operations
- Refactor the challenge stats management to ensure consistent updates across all UI components
- Ensure progress bars in the challenge list update immediately after successful check-in

## Capabilities

### New Capabilities
- *None - this is a bug fix*

### Modified Capabilities
- `challenge-state-sync`: Update challenge state synchronization requirements to ensure stats refresh after check-in operations

## Impact

- Frontend: `packages/site/src/components/challenge_view.tsx` and `packages/site/src/lib/store/challenge.ts`
- UI Components: Challenge list progress bars and current challenge detail view
- User Experience: Real-time progress updates after check-in operations
