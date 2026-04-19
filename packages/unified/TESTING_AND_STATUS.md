# Unified Package: Functional Status & Testing Guide

> **Version**: 0.3.7 | **Scope**: `@saili/unified` — Markdown processing, custom syntax extensions, and editor decorations.

---

## 1. Package Architecture Overview

```
packages/unified/src/
├── remark/          # Custom Markdown syntax parsers (MDAST extensions)
├── rehype/          # HTML transformation plugins (HAST transforms)
├── decorations/     # Editor decoration providers (VS Code style)
├── types.ts         # AST node types & DendronASTTypes enum
├── utilsv5.ts       # Server-side processor factory (MDUtilsV5)
├── utilsWeb.ts      # Browser-side processor factory (MDUtilsV5Web)
├── __tests__/       # Test suites & fixtures
└── remark/__tests__/# Plugin-level unit tests
```

### Processing Pipeline

```
Markdown Input
    ↓
remark-parse (CommonMark)
    ↓
remark plugins (custom tokenizers) → MDAST with DendronASTTypes nodes
    ↓
remark-rehype
    ↓
rehype plugins (HTML transforms) → HAST
    ↓
rehype-stringify → HTML Output
```

**Processor Factories:**
- `MDUtilsV5.procRehypeFull()` — Server-side, full pipeline (used in tests via `processNoteFull()`)
- `MDUtilsV5Web.procRehypeWeb()` — Browser-side, for preview builds

---

## 2. Functional Status: Remark Plugins

| Plugin | File | Status | Tests | Description |
|--------|------|--------|-------|-------------|
| `wikiLinks` | `remark/wikiLinks.ts` | ✅ Active | ✅ `wikiLinks.test.ts` | `[[target]]`, `[[alias\|target]]`, `[[target#anchor]]` wiki-style links. Uses micromark tokenization. |
| `hashtags` | `remark/hashtag.ts` | ✅ Active | ✅ `hashtag.test.ts` | `#tag` tags, shorthand for `[[tags.tag]]`. Regex-based tokenizer. |
| `zdocTags` | `remark/zdocTags.ts` | ✅ Active | ✅ `zdocTags.test.ts` + `tag.test.ts` | `\cite{key}` ZDoc citations. Requires `enableZDocTags` config. |
| `blockAnchors` | `remark/blockAnchors.ts` | ✅ Active | ❌ None | `^anchor-id` block references. Used by noteRefs for range selection. |
| `noteRefsV2` | `remark/noteRefsV2.ts` | ✅ Active | ❌ None | `![[note-ref]]` transclusion. Complex: wildcard refs, anchor ranges, pretty refs, nesting limit. |
| `extendedImage` | `remark/extendedImage.ts` | ✅ Active | ❌ None | `![alt](url){props}` images with YAML props. Falls back to regular image on bad props. |
| `sailzenCite` | `remark/sailzenCite.ts` | ✅ Active | ❌ None | `::cite[foo, bar]` inline citations. Multi-dest rendering (MD/HTML/DOC). |
| `sailzenFigure` | `remark/sailzenFigure.ts` | ✅ Active | ❌ None | `::figure[caption](src){opts}` figure directives. Option parser for key=value pairs. |
| `abbr` | `remark/abbr.ts` | ✅ Active | ❌ None | Abbreviation expansion plugin. |
| `dendronPub` | `remark/dendronPub.ts` | ✅ Active | ❌ None | Publishing-time link resolution & note ref HAST conversion. |
| `dendronPreview` | `remark/dendronPreview.ts` | ✅ Active | ❌ None | Preview-mode link resolution. |
| `transformLinks` | `remark/transformLinks.ts` | ✅ Active | ❌ None | Link transformation utilities. |
| `backlinks` | `remark/backlinks.ts` | ✅ Active | ❌ None | Backlink injection during processing. |
| `backlinksHover` | `remark/backlinksHover.ts` | ✅ Active | ❌ None | Hover preview for backlinks. |
| `hierarchies` | `remark/hierarchies.ts` | ✅ Active | ❌ None | Hierarchy-aware processing. |
| `publishSite` | `remark/publishSite.ts` | ✅ Active | ❌ None | Site publishing helpers. |

### Remark Plugin Pattern

All remark plugins follow the same structure:

```ts
const plugin: Plugin<[PluginOpts?]> = function (this: Processor, _opts?) {
  attachParser(this);      // Register tokenizer + locator
  if (this.Compiler != null) {
    attachCompiler(this);  // Register AST-to-target visitor
  }
};
```

**Parser attachment:**
1. `locator(value, fromIndex)` — Returns index of syntax start
2. `inlineTokenizer(eat, value)` — Regex match + `eat(match[0])(node)`
3. Register in `Parser.prototype.inlineTokenizers` and `inlineMethods`

**Compiler attachment:**
1. Register visitor in `Compiler.prototype.visitors[DendronASTTypes.X]`
2. Switch on `DendronASTDest` (MD_DENDRON / MD_REGULAR / HTML / DOC_EXPORT / DOC_PREVIEW)

---

## 3. Functional Status: Rehype Plugins

| Plugin | File | Status | Tests | Description |
|--------|------|--------|-------|-------------|
| `wrap` | `rehype/wrap.ts` | ✅ Active | ✅ `wrap.test.ts` | Wraps HAST nodes matching a CSS selector in a wrapper element. |
| `mermaid-noop` | `rehype/mermaid-noop.ts` | ✅ Active | ❌ None | No-op placeholder for mermaid diagrams (avoids playwright dep). |

---

## 4. Functional Status: Decorations

Decorations analyze parsed AST to produce IDE highlighting (ranges + types). They do **not** generate HTML.

| Decoration | File | Status | Tests | Description |
|------------|------|--------|-------|-------------|
| `wikiLinks` | `decorations/wikilinks.ts` | ✅ Active | ❌ None | Highlight wiki link ranges. |
| `hashTags` | `decorations/hashTags.ts` | ✅ Active | ❌ None | Highlight hashtag ranges. |
| `zdocTags` | `decorations/zdocTags.ts` | ✅ Active | ❌ None | Highlight ZDoc tag ranges. |
| `blockAnchors` | `decorations/blockAnchors.ts` | ✅ Active | ❌ None | Highlight block anchor ranges. |
| `references` | `decorations/references.ts` | ✅ Active | ❌ None | Highlight note reference ranges. |
| `frontmatter` | `decorations/frontmatter.ts` | ✅ Active | ❌ None | Frontmatter region decoration. |
| `taskNotes` | `decorations/taskNotes.ts` | ✅ Active | ❌ None | Task note decorations. |
| `diagnostics` | `decorations/diagnostics.ts` | ✅ Active | ❌ None | Diagnostic warnings (bad frontmatter, etc.). |
| `decorations.ts` | `decorations/decorations.ts` | ✅ Active | ❌ None | Dispatcher: `runDecorator()` + `runAllDecorators()`. |

---

## 5. Test Coverage Matrix

### Existing Tests

| Test File | What It Tests | Approach |
|-----------|---------------|----------|
| `mdutilsv5.test.ts` | Full `procRehypeFull` pipeline | Integration: note → processor → HTML string assertions |
| `utilsWeb.test.ts` | Full `procRehypeWeb` pipeline | Integration: note → processor → HTML string assertions |
| `utils.test.ts` | Utility functions | Unit tests |
| `hello.test.ts` | Sanity check | Smoke test |
| `remark/__tests__/wikiLinks.test.ts` | Wiki link regex + utils + full processor | Regex unit + integration via `processNoteFull()` |
| `remark/__tests__/hashtag.test.ts` | Hashtag regex + utils + full processor | Regex unit + integration |
| `remark/__tests__/zdocTags.test.ts` | ZDoc tag regex + utils + full processor | Regex unit + integration |
| `remark/__tests__/tag.test.ts` | ZDoc regex edge cases | Regex unit |
| `rehype/__tests__/wrap.test.ts` | `wrap` plugin | HAST transform test |

### Coverage Gaps (Priority Order)

| Module | Priority | Why | Suggested Test Approach |
|--------|----------|-----|------------------------|
| `sailzenCite` | **High** | Custom syntax, multi-dest rendering | Regex + AST node creation + HTML output per dest |
| `sailzenFigure` | **High** | Custom syntax, option parser | Regex + option parsing + HTML/MD round-trip |
| `blockAnchors` | **High** | Core feature, noteRefs dependency | Regex + block anchor node + MD_DENDRON round-trip |
| `extendedImage` | **Medium** | Custom syntax, YAML props | Regex + props parsing + HTML rendering |
| `noteRefsV2` | **Medium** | Complex but critical | Mock `noteCacheForRenderDict`, test basic transclusion |
| `decorations/*` | **Medium** | All 8 decorators untested | AST → decoration range assertions |
| `dendronPub` | **Low** | Publishing logic | Integration with mock engine |
| `backlinks` | **Low** | Backlink injection | Mock engine + assert backlinks in output |
| `hierarchies` | **Low** | Hierarchy processing | TBD based on usage |

---

## 6. How to Test Custom Markdown Annotation Syntax

This section formalizes the testing pattern used by `wikiLinks`, `hashtag`, and `zdocTags`.

### Pattern A: Regex & Utils (Fast, Isolated)

Test the regex patterns and utility functions directly without a processor.

```ts
// src/remark/__tests__/sailzenCite.test.ts
import { CITE_REGEX, sailzenCite } from "../sailzenCite";

describe("sailzenCite regex", () => {
  test("should match basic cite", () => {
    const match = CITE_REGEX.exec("::cite[foo, bar]");
    expect(match).not.toBeNull();
    expect(match?.[1]).toBe("foo, bar");
  });

  test("should not match without keys", () => {
    expect(CITE_REGEX.exec("::cite[]")).toBeNull();
  });
});
```

### Pattern B: AST Node Creation (Plugin Isolation)

Build a minimal pipeline to verify the plugin creates the correct AST node.

```ts
import { remark } from "remark";
import remarkParse from "remark-parse";
import { sailzenCite } from "../sailzenCite";
import { DendronASTTypes } from "../../types";

describe("sailzenCite AST", () => {
  test("should create sailzenCite node", async () => {
    const processor = remark()
      .use(remarkParse)
      .use(sailzenCite);

    const ast = processor.parse("::cite[foo, bar]");
    // Traverse AST to find our custom node
    const citeNode = findNodeByType(ast, DendronASTTypes.SAILZEN_CITE);
    expect(citeNode).toBeDefined();
    expect(citeNode.keys).toEqual(["foo", "bar"]);
  });
});
```

**Note:** Some tokenizers (hashtag, zdocTags) check `ConfigUtils.getWorkspace(config)` via `MDUtilsV5.getProcData(proc)`. For these, use Pattern C.

### Pattern C: Full Processor Integration (Recommended)

Use the existing test helpers to process through the full pipeline.

```ts
import { createTestNoteWithBody } from "../../__tests__/fixtures/testNotes";
import { processNoteFull } from "../../__tests__/utils/testHelpers";

describe("sailzenCite with full processor", () => {
  test("should render cite in HTML", async () => {
    const note = createTestNoteWithBody("See ::cite[foo, bar] for details.");
    const html = await processNoteFull(note);
    expect(html).toContain("<sup>");
    expect(html).toContain("[foo, bar]");
  });
});
```

**Key helpers from `testHelpers.ts`:**

| Helper | Purpose |
|--------|---------|
| `createTestNoteWithBody(body)` | Creates a `NoteProps` with given markdown body |
| `createTestNoteWithWikiLinks(links)` | Creates note with `[[link]]` bodies |
| `createTestNoteWithHashtags(tags)` | Creates note with `#tag` bodies |
| `processNoteFull(note, flavor?)` | Runs note through `MDUtilsV5.procRehypeFull` → HTML string |
| `createFullTestProcessor(note, flavor?)` | Returns processor instance for custom assertions |

### Pattern D: Multi-Destination Compiler Tests

For plugins with `attachCompiler` that switch on `DendronASTDest`:

```ts
import { DendronASTDest } from "../../types";
import { MDUtilsV5 } from "../../utilsv5";

describe("sailzenCite compiler", () => {
  test("should round-trip in MD_DENDRON mode", async () => {
    const note = createTestNoteWithBody("::cite[foo, bar]");
    const proc = MDUtilsV5.procRehypeFull(
      { noteToRender: note, fname: note.fname, vault: note.vault, config: createTestConfig(), dest: DendronASTDest.MD_DENDRON },
      { flavor: ProcFlavor.REGULAR }
    );
    const result = await proc.process(note.body);
    expect(result.toString()).toContain("::cite[foo, bar]");
  });
});
```

---

## 7. Custom Syntax Catalog

| Syntax | AST Type | Plugin | Example | Destinations |
|--------|----------|--------|---------|-------------|
| `[[target]]` | `wikiLink` | `wikiLinks` | `[[hello]]` | MD_DENDRON, HTML |
| `[[alias\|target]]` | `wikiLink` | `wikiLinks` | `[[hi\|hello]]` | MD_DENDRON, HTML |
| `#tag` | `hashtag` | `hashtags` | `#important` | MD_DENDRON, MD_REGULAR |
| `\cite{key}` | `zdoctag` | `zdocTags` | `\cite{foo}` | MD_DENDRON |
| `^anchor` | `blockAnchor` | `blockAnchors` | `^my-anchor` | MD_DENDRON, MD_REGULAR, MD_ENHANCED_PREVIEW |
| `![[note]]` | `refLinkV2` | `noteRefsV2` | `![[daily.journal]]` | MD_DENDRON, HTML |
| `![alt](url){props}` | `extendedImage` | `extendedImage` | `![](img.png){width: 100}` | MD_DENDRON, MD_REGULAR, MD_ENHANCED_PREVIEW |
| `::cite[keys]` | `sailzenCite` | `sailzenCite` | `::cite[foo, bar]` | MD_DENDRON, HTML, DOC_EXPORT, DOC_PREVIEW |
| `::figure[cap](src){opts}` | `sailzenFigure` | `sailzenFigure` | `::figure[Teaser](fig1){width="80%"}` | MD_DENDRON, HTML, DOC_EXPORT, DOC_PREVIEW |

### Reserved / Planned Types (in `DendronASTTypes` but not fully implemented)

| Type | Status | Description |
|------|--------|-------------|
| `SAILZEN_TABLE` | 🔶 Planned | Advanced table directive |
| `SAILZEN_MATH_ENV` | 🔶 Planned | `::theorem`, `::proof`, `::definition` |
| `SAILZEN_ALGORITHM` | 🔶 Planned | `::algorithm` environment |
| `SAILZEN_IF_FORMAT` | 🔶 Planned | `::if-format[latex]` conditional |

---

## 8. Running Tests

```bash
# All unified tests
pnpm run test:unified

# Single test file
pnpm jest packages/unified/src/remark/__tests__/hashtag.test.ts

# With coverage
pnpm jest packages/unified --coverage
```

**ESM Note:** Jest runs with `--experimental-vm-modules` due to ESM usage in `unified` v11.

---

## 9. Adding a New Custom Syntax: Checklist

1. **Define AST type** in `src/types.ts` (add to `DendronASTTypes` enum + node interface)
2. **Implement remark plugin** in `src/remark/mySyntax.ts`:
   - `attachParser()` with locator + tokenizer
   - `attachCompiler()` with multi-dest visitor
3. **Register plugin** in `src/utilsv5.ts` (`procRehypeFull`) and/or `src/utilsWeb.ts`
4. **Add decoration** in `src/decorations/` (if IDE highlighting needed)
   - Register in `src/decorations/decorations.ts` `runDecorator()` dispatcher
5. **Write tests** in `src/remark/__tests__/mySyntax.test.ts`:
   - Regex unit tests
   - Full processor integration tests via `processNoteFull()`
   - If compiler has multiple destinations, test each
6. **Update this document** with the new syntax entry
