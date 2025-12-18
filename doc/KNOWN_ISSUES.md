# Known Issues

This document tracks known issues in the SailZen VSCode extension that are pending fixes.

## Third-Party Library Issues

### `remark-variables@1.4.9` - Undeclared Variable Bug

**Package**: `remark-variables@1.4.9`  
**Location**: `packages/unified/package.json`  
**Error**: `ReferenceError: actual is not defined`

**Description**:  
The `remark-variables` library has a bug in its `lib/utils.js` file where the variable `actual` is used without being declared with `var`, `let`, or `const`. This causes a `ReferenceError` in strict mode.

**Stack Trace**:
```
at is4 (extension.js:97155:16)
at fences (extension.js:97133:11)
at Object.settings (extension.js:97122:23)
at apply.variables3 (extension.js:97330:25)
at apply.freeze (extension.js:275065:36)
at apply.parse (extension.js:275089:10)
at _RemarkUtils.getNodePositionPastFrontmatter (extension.js:283511:25)
```

**Impact**:  
- Affects markdown parsing/folding functionality
- Does not block core Calendar View or Tree View functionality

**Workaround**:  
Use `pnpm patch` to fix the undeclared variable:

```bash
pnpm patch remark-variables@1.4.9
# Edit node_modules/.pnpm_patches/remark-variables@1.4.9/lib/utils.js
# Change line 51 from: actual = match[1].trim()
# To: var actual = match[1].trim()
pnpm patch-commit "path/to/patch/folder"
```

**Workaround Applied**:  
A globalThis polyfill has been added in `packages/vscode_plugin/src/extension.ts` to define these variables globally before the library code runs:

```typescript
// Workaround for remark-variables@1.4.9 bug
(globalThis as any).actual = undefined;
(globalThis as any).val = undefined;
```

**Status**: Workaround applied

---

## Console Warnings

### `DendronSideGraphPanel is an invalid or empty name`

**Description**:  
The webview tries to render a component named `DendronSideGraphPanel` which is not registered in `packages/dendron_plugin_views/src/index.tsx`.

**Impact**:  
- Console warning only
- Graph panel view will not render

**Fix Required**:  
Register `DendronSideGraphPanel` component in the `COMPONENTS` registry in `packages/dendron_plugin_views/src/index.tsx`.

**Status**: Pending implementation

---

*Last updated: 2025-12-18*
