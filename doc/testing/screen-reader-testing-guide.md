# Screen Reader Testing Guide for Outline Components

## Overview

This document provides guidelines for testing the outline virtualization and pagination features with screen readers (NVDA on Windows, VoiceOver on macOS).

## Prerequisites

### Windows (NVDA)
- Install NVDA from: https://www.nvaccess.org/download/
- Start NVDA with `Ctrl + Alt + N`

### macOS (VoiceOver)
- Enable VoiceOver: `Cmd + F5` or `System Preferences > Accessibility > VoiceOver`
- Learn VoiceOver gestures: https://www.apple.com/voiceover/info/guide/

## Test Scenarios

### 1. Virtualized List Navigation (Test 9.1, 9.4, 9.5)

**Expected Behavior:**
- Screen reader announces list item position (e.g., "Item 1 of 1000")
- ARIA labels are read correctly
- Keyboard navigation works with arrow keys

**Test Steps:**
1. Navigate to the outline panel
2. Verify screen reader announces: "Outline tree, list with [N] items"
3. Use arrow keys to navigate
4. Verify each item is announced with its title and position
5. Check that expanded/collapsed state is announced

**Pass Criteria:**
- [ ] Position announcements are accurate
- [ ] All ARIA labels are read
- [ ] No "clickable" spam without context
- [ ] Focus is clearly indicated

### 2. Pagination Loading Announcements (Test 9.2)

**Expected Behavior:**
- Screen reader announces when new content loads
- Loading states are communicated
- No silent updates

**Test Steps:**
1. Scroll to bottom of outline
2. Wait for pagination trigger
3. Verify announcement: "Loading more items"
4. After load, verify: "[N] more items loaded"

**Pass Criteria:**
- [ ] Loading announcement is clear
- [ ] Success announcement includes item count
- [ ] Error states are announced if loading fails

### 3. Evidence Expansion (Test 5.5, 9.6)

**Expected Behavior:**
- "Show full evidence" button is accessible
- Evidence content is readable when expanded
- aria-expanded attribute updates correctly

**Test Steps:**
1. Navigate to a node with evidence
2. Find "Show full evidence" button
3. Activate it (Enter or Space)
4. Verify screen reader announces: "Evidence expanded"
5. Read through evidence content
6. Collapse and verify: "Evidence collapsed"

**Pass Criteria:**
- [ ] Button has clear label
- [ ] Expanded state is announced
- [ ] Evidence content is readable
- [ ] aria-expanded updates correctly

### 4. Keyboard Navigation (Test 9.4, 9.5)

**Expected Behavior:**
- All functionality is accessible via keyboard
- Focus management is clear
- No keyboard traps

**Test Steps:**
1. Tab into outline panel
2. Use arrow keys to navigate up/down
3. Use Enter to expand/collapse
4. Use Home/End to jump to first/last item
5. Test page up/down for faster navigation

**Keyboard Shortcuts:**
- `↑/↓` - Navigate between items
- `→` - Expand node (if collapsed)
- `←` - Collapse node (if expanded)
- `Enter` - Toggle expand/collapse
- `Home` - Jump to first item
- `End` - Jump to last loaded item
- `Page Up/Down` - Navigate 10 items at a time

**Pass Criteria:**
- [ ] All shortcuts work
- [ ] Focus is visible
- [ ] No keyboard traps
- [ ] Focus is not lost during pagination

### 5. Dynamic Content Updates

**Expected Behavior:**
- Newly loaded items are announced
- Virtual scrolling doesn't confuse screen reader
- Content changes are communicated

**Test Steps:**
1. Navigate to middle of large outline
2. Scroll to trigger pagination
3. Verify new items are accessible
4. Check that focus stays on current item
5. Navigate to newly loaded items

**Pass Criteria:**
- [ ] New items are announced
- [ ] Focus is maintained
- [ ] No focus jumps to top unexpectedly

## Known Issues and Workarounds

### Issue: Virtual Lists May Announce Incorrect Item Count
**Workaround:** Use `aria-setsize="-1"` for unknown total size

### Issue: Fast Scrolling Can Miss Announcements
**Workaround:** Implement `aria-live="polite"` regions for important updates

### Issue: aria-expanded Not Always Announced
**Workaround:** Ensure button controls the expandable region via `aria-controls`

## Testing Checklist

- [ ] NVDA on Windows 10/11
- [ ] VoiceOver on macOS
- [ ] VoiceOver on iOS (if mobile support needed)
- [ ] TalkBack on Android (if mobile support needed)
- [ ] Keyboard-only navigation test
- [ ] High contrast mode test
- [ ] Zoom 200% test

## Accessibility Features Implemented

1. **ARIA Labels** - All list items have descriptive labels
2. **aria-expanded** - Nodes indicate expand/collapse state
3. **aria-live** - Loading and update announcements
4. **Keyboard Navigation** - Full keyboard support
5. **Focus Management** - Visible focus indicators
6. **Semantic HTML** - Proper list and button structures

## Reporting Issues

When reporting accessibility issues, include:
1. Screen reader and version
2. Browser and version
3. OS and version
4. Exact steps to reproduce
5. Expected vs actual behavior
6. Screenshot/video if possible

## Additional Resources

- [ARIA Authoring Practices Guide](https://www.w3.org/WAI/ARIA/apg/)
- [NVDA Documentation](https://www.nvaccess.org/documentation/)
- [VoiceOver Guide](https://www.apple.com/voiceover/info/guide/)
- [WebAIM Screen Reader Survey](https://webaim.org/projects/screenreadersurvey/)
