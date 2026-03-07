## Context

The Challenge page (`packages/site/src/pages/project.tsx`) has a bug in the Challenge (打卡挑战) tab. When a user successfully checks in (打卡成功), the progress bar in the challenge list (left sidebar) does not update in real-time. The user must manually refresh the page to see the updated progress.

**Root Cause Analysis:**
1. The challenge list maintains its own stats state (`challengeStatsMap`) locally in `ChallengeView` component
2. After check-in, the store's `checkInSuccess` action calls `fetchChallengeDetail()` and `fetchActiveChallenges()`
3. While `fetchChallengeDetail()` updates `currentStats` in the store, it does NOT update the local `challengeStatsMap`
4. The `fetchActiveChallenges()` only updates the challenge list data, not the associated stats
5. This creates a synchronization gap between the store state and the local component state

**Current State:**
- `ChallengeView` component: Manages `challengeStatsMap` as local state
- `useChallengeStore`: Manages global state including `currentStats` for the selected challenge
- Stats are loaded asynchronously via `api_get_challenge_detail()` in `loadSingleChallengeStats()`

## Goals / Non-Goals

**Goals:**
- Fix the real-time progress bar update issue after check-in
- Ensure consistent state synchronization between check-in actions and UI updates
- Minimize code changes while fixing the core issue
- Maintain performance - avoid excessive API calls

**Non-Goals:**
- Refactoring the entire challenge system architecture
- Changing the backend API
- Adding new features beyond the bug fix
- Modifying the UI design or user flow

## Decisions

**Decision 1: Refresh challenge stats after check-in operations**
- After `checkInSuccess`, `checkInFailed`, or `resetCheckIn` actions complete, trigger a refresh of the affected challenge's stats in `challengeStatsMap`
- **Rationale**: This directly addresses the root cause - the local stats map is not updated after check-in
- **Alternative considered**: Moving all stats to the global store - rejected because it would require significant refactoring of the component

**Decision 2: Use a refresh flag/callback mechanism**
- Add a mechanism to notify the component that stats need refreshing after store operations complete
- **Rationale**: The component owns the `challengeStatsMap` state, so it needs to be notified when to refresh
- **Implementation**: Add a callback parameter or use a refresh trigger in the store actions

**Decision 3: Reuse existing `loadSingleChallengeStats` function**
- After check-in success, call the existing `loadSingleChallengeStats` function with the affected challenge ID
- **Rationale**: This function already handles fetching stats and updating the local map, no need to duplicate logic

## Risks / Trade-offs

**Risk: Race condition between multiple check-ins**
- If user rapidly clicks check-in, multiple requests might be in flight
- **Mitigation**: The existing `loadingChallengeIds` ref already prevents duplicate requests for the same challenge

**Risk: Performance impact of additional API calls**
- Refreshing stats after each check-in adds one API call
- **Mitigation**: The API call is lightweight (just fetching challenge detail) and only happens once per check-in action

**Risk: Component re-render overhead**
- Updating `challengeStatsMap` will trigger re-renders of the challenge list
- **Mitigation**: This is the desired behavior - the UI should update to reflect new progress

## Migration Plan

**Deployment:**
1. Update `useChallengeStore` actions (`checkInSuccess`, `checkInFailed`, `resetCheckIn`) to return the challenge ID or success status
2. Update `ChallengeView` component to refresh stats after check-in operations complete
3. Test the fix locally with multiple challenges
4. Deploy to production

**Rollback:**
- Changes are localized to two files and can be easily reverted
- No database migrations or API changes required

## Open Questions

None - the issue is well-understood and the fix is straightforward.
