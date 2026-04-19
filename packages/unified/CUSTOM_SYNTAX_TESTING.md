# Custom Markdown Syntax Testing Guide

> For `@saili/unified` contributors adding new remark plugins.

## Testing Philosophy

Custom syntax plugins in this package follow a **4-tier testing pattern**. Because tokenizers depend on `MDUtilsV5.getProcData(proc).config`, isolated `remark().use(plugin)` tests are unreliable. The reliable path is:

1. **Test regexes in isolation** — fast, deterministic, no processor context needed
2. **Test utility functions** — pure functions that extract data from matches
3. **Skip isolated plugin tests** — remark-parse tokenizers need full `MDUtilsV5` context
4. **Test via `processNoteFull`** — full pipeline integration test with real HTML output

## 4-Tier Test Structure

### Tier 1: Regex Unit Tests

Every custom syntax exports a `*_REGEX` (start-anchored) and `*_REGEX_LOOSE` (anywhere). Test both.

```ts
describe("MY_FEATURE_REGEX", () => {
  test("should match at start", () => {
    const match = MY_FEATURE_REGEX.exec("::myFeature[value]");
    expect(match).not.toBeNull();
    expect(match?.[1]).toBe("value");
  });

  test("should not match in middle of text", () => {
    const match = MY_FEATURE_REGEX.exec("text ::myFeature[value]");
    expect(match).toBeNull();
  });
});

describe("MY_FEATURE_REGEX_LOOSE", () => {
  test("should match anywhere", () => {
    const match = MY_FEATURE_REGEX_LOOSE.exec("text ::myFeature[value]");
    expect(match).not.toBeNull();
  });
});
```

### Tier 2: Utility Function Tests

Test pure helper functions like `matchMyFeature()`, `extractXFromMatch()`.

```ts
describe("MyFeatureUtils", () => {
  test("matchMyFeature should extract value", () => {
    const result = MyFeatureUtils.matchMyFeature("::myFeature[test]");
    expect(result).toBe("test");
  });

  test("matchMyFeature should return undefined for invalid input", () => {
    const result = MyFeatureUtils.matchMyFeature("invalid");
    expect(result).toBeUndefined();
  });
});
```

### Tier 3: Skipped Isolated Plugin Tests

Keep the describe block as a placeholder. The tokenizers require `MDUtilsV5` processor data that `remark().use()` alone cannot provide.

```ts
describe.skip("myFeature plugin integration", () => {
  test("should parse in markdown", () => {
    // Skipped: requires full processor context
  });
});
```

### Tier 4: Full Processor Integration Tests

Use `processNoteFull(note)` from `__tests__/utils/testHelpers.ts`. It runs the entire remark→rehype→HTML pipeline.

```ts
import { createTestNoteWithBody } from "../../__tests__/fixtures/testNotes";
import { processNoteFull } from "../../__tests__/utils/testHelpers";

describe("myFeature with full processor", () => {
  test("should render in HTML", async () => {
    const note = createTestNoteWithBody("Some ::myFeature[value] text");
    const html = await processNoteFull(note);
    expect(html).toContain("value");
  });
});
```

## Test Fixtures

Use helpers from `src/__tests__/fixtures/testNotes.ts`:

| Function | Purpose |
|----------|---------|
| `createTestNoteWithBody(body)` | Note with arbitrary markdown body |
| `createTestNoteWithWikiLinks(links[])` | Body with `[[link]]` entries |
| `createTestNoteWithHashtags(tags[])` | Body with `#tag` entries |
| `createTestConfig()` | Minimal workspace config |
| `createTestVault()` | Minimal vault descriptor |

## File Naming Convention

Place tests alongside the plugin in `src/remark/__tests__/`:

```
src/remark/
  myFeature.ts
  __tests__/
    myFeature.test.ts
```

## Complete Template

```ts
/**
 * Tests for myFeature remark plugin
 */

import {
  myFeature,
  MY_FEATURE_REGEX,
  MY_FEATURE_REGEX_LOOSE,
  MyFeatureUtils,
} from "../myFeature";
import { createTestNoteWithBody } from "../../__tests__/fixtures/testNotes";
import { processNoteFull } from "../../__tests__/utils/testHelpers";
import { DendronASTTypes } from "../../types";

describe("myFeature plugin", () => {
  // === Tier 1: Regex ===
  describe("MY_FEATURE_REGEX", () => {
    test("should match at start", () => {
      const match = MY_FEATURE_REGEX.exec("::myFeature[test]");
      expect(match).not.toBeNull();
      expect(match?.[1]).toBe("test");
    });

    test("should not match in middle", () => {
      expect(MY_FEATURE_REGEX.exec("text ::myFeature[test]")).toBeNull();
    });
  });

  describe("MY_FEATURE_REGEX_LOOSE", () => {
    test("should match anywhere", () => {
      const match = MY_FEATURE_REGEX_LOOSE.exec("text ::myFeature[test]");
      expect(match).not.toBeNull();
    });
  });

  // === Tier 2: Utilities ===
  describe("MyFeatureUtils", () => {
    test("matchMyFeature extracts value", () => {
      expect(MyFeatureUtils.matchMyFeature("::myFeature[test]")).toBe("test");
    });
  });

  // === Tier 3: Skipped (needs MDUtilsV5 context) ===
  describe.skip("myFeature plugin integration", () => {
    test("should parse in markdown", () => {
      // Skipped: requires full processor context
    });
  });

  // === Tier 4: Full processor ===
  describe("myFeature with full processor", () => {
    test("should render in HTML", async () => {
      const note = createTestNoteWithBody("Hello ::myFeature[world]");
      const html = await processNoteFull(note);
      expect(html).toContain("world");
    });
  });
});
```

## Running Tests

From repo root:

```bash
# Run all unified tests
pnpm test:unified

# Run a specific test file
pnpm --filter="./packages/unified" exec cross-env NODE_OPTIONS=--experimental-vm-modules jest src/remark/__tests__/myFeature.test.ts

# Watch mode
pnpm --filter="./packages/unified" exec cross-env NODE_OPTIONS=--experimental-vm-modules jest --watch
```

## Config-Gated Syntax

If your plugin reads `config.enableMyFeature`, the `processNoteFull` helper uses a default test config. If your feature is disabled by default, enable it in the test note or mock the config.

## Common Pitfalls

1. **Regex anchor mismatch**: `MY_FEATURE_REGEX` must be start-anchored (`^...`) because remark inline tokenizers receive text from the current position onward.
2. **Locator function**: Always provide a `locator` on the inlineTokenizer so remark can find your syntax efficiently.
3. **Insertion order**: Use `inlineMethods.splice(inlineMethods.indexOf("link"), 0, "myFeature")` to insert before `link` (or `"text"` for text-priority syntax).
4. **Compiler destination**: Always handle all `DendronASTDest` values or throw a descriptive `DendronError`.
5. **HTML assertions**: `processNoteFull` returns a full HTML document string; use `.toContain()` for assertions rather than exact matching.
