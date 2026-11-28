# SailZen VSCode Plugin — Code Map & Technical Debt Review

> Document version: 2025-06-09  
> Scope: `packages/vscode_plugin/src/docEngine` + `commands/Zotero.ts` + related services  
> Author: AI Agent (context-compaction aware)

---

## 1. Code Map

### 1.1 High-level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        VSCode Extension Layer                            │
│  ┌────────────────────┐  ┌────────────────────┐  ┌──────────────────┐  │
│  │ ExportNoteCommand  │  │CompileDocumentCmd  │  │ Zotero Commands  │  │
│  │ (user interaction) │  │ (build orchestration)│  │ (citation Mgmt)  │  │
│  └─────────┬──────────┘  └─────────┬──────────┘  └────────┬─────────┘  │
└────────────┼───────────────────────┼──────────────────────┼────────────┘
             │                       │                      │
             ▼                       ▼                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         DocEngine Public API                             │
│  resolveProfile / resolveProfileAST                                      │
│  assembleDocument / assembleDocumentAST + astToAssembledDocument         │
│  generateLatex / generateTypst / generateMarkdown                        │
│  renderTemplate / templateLoader / compileService                        │
└─────────────────────────────────────────────────────────────────────────┘
             │                       │
             ▼                       ▼
┌──────────────────────┐    ┌────────────────────────┐
│   Legacy Path        │    │   AST Path (New)       │
│  (regex-driven)      │    │  (unified/remark-based)│
├──────────────────────┤    ├────────────────────────┤
│ profileResolver.ts   │    │ astProfileResolver.ts  │
│ documentAssembler.ts │    │ astDocumentAssembler.ts│
│ latexBackend.ts      │◄──►│ astLatexTransformer.ts │
│   └─ markdownToLatex │    │   └─ mdastToLatex      │
│ typstBackend.ts      │    │  (Typst AST missing)   │
│ markdownBackend.ts   │    │  (MD AST missing)      │
└──────────────────────┘    └────────────────────────┘
```

### 1.2 File Inventory

| File | Lines | Responsibility | Path Status |
|------|-------|----------------|-------------|
| `docEngine/index.ts` | 40 | Public barrel export | ✅ Stable |
| `docEngine/profileResolver.ts` | 323 | Legacy profile resolution (string regex scan) | ⚠️ Legacy |
| `docEngine/astProfileResolver.ts` | 251 | AST-based profile resolution | 🔶 New, partial |
| `docEngine/documentAssembler.ts` | 323 | String-based note-ref expansion | ⚠️ Legacy |
| `docEngine/astDocumentAssembler.ts` | 343 | AST-based transclusion (MDAST-level) | 🔶 New, partial |
| `docEngine/latexBackend.ts` | 794 | LaTeX generation (regex fallback + AST gate) | ⚠️ Dual path |
| `docEngine/astLatexTransformer.ts` | 392 | AST → LaTeX recursive transformer | 🔶 New, active |
| `docEngine/typstBackend.ts` | 813 | Typst generation (fully regex) | 🔴 Debt |
| `docEngine/markdownBackend.ts` | 281 | Markdown generation (fully regex) | 🔴 Debt |
| `docEngine/templateEngine.ts` | 488 | Built-in templates + variable resolution | ⚠️ Mixed |
| `docEngine/templateLoader.ts` | 442 | External template discovery + `{{var}}` engine | ✅ Stable |
| `docEngine/compileService.ts` | 245 | latexmk / xmake / typst CLI invocation | ⚠️ Minimal |
| `commands/Zotero.ts` | 190 | Zotero CAYW picker, bib note import | ⚠️ Ad-hoc |
| `services/ZoteroService.ts` | 189 | BBT JSON-RPC client, BibTeX parsing | ⚠️ Fragile |
| `commands/ExportNoteCommand.ts` | 547 | Main export UI + dispatch | ✅ Stable |
| `commands/CompileDocumentCommand.ts` | 156 | Compilation UI + dispatch | ✅ Stable |

### 1.3 Unified / AST Pipeline (Cross-package)

```
packages/unified/src/
├── remark/sailzenCite.ts      ::cite[key1, key2]  → sailzenCite node
├── remark/sailzenFigure.ts    ::figure[cap](src)  → sailzenFigure node
├── remark/sailzenBlocks.ts    ::theorem/::table/… → sailzenMathEnv / sailzenTable / sailzenAlgorithm / sailzenIfFormat
├── utilsv5.ts                 Pipeline builder; enables sailzenCite/Figure/Blocks ONLY when dest = DOC_EXPORT | DOC_PREVIEW
└── types.ts                   SailASTTypes constants
```

**Critical Gap**: `astDocumentAssembler.ts` uses a **bare** `remark().use(remarkParse)` without the SailZen extensions.  
This means `assembleDocumentAST()` produces an AST that **does not contain** `sailzenCite`, `sailzenFigure`, or `sailzenBlocks` nodes.  
The AST path therefore falls back to treating them as plain text, and `astLatexTransformer.ts` never sees the custom nodes.

---

## 2. Technical Debt Register

### 2.1 🔴 High Severity — Structural Debt

| ID | Location | Debt Description | Impact | Migration Strategy |
|----|----------|------------------|--------|-------------------|
| DEBT-01 | `latexBackend.ts` `markdownToLatex()` | 250+ line regex protect/restore pipeline. Inline math regex uses lookbehind/lookahead which fails on some JS engines. | Fragile, unmaintainable, cannot extend for new syntax | Already gated behind `useAST` flag; complete removal once AST path is proven |
| DEBT-02 | `typstBackend.ts` entire file | 100% regex-driven, mirrors latexBackend protect/restore pattern. No AST gate. | Any markdown syntax change requires dual maintenance; Typst always takes fragile path | Build `astTypstTransformer.ts` analogous to `astLatexTransformer.ts` |
| DEBT-03 | `markdownBackend.ts` entire file | 100% regex-driven protect/restore. | Same as above | Build `astMarkdownTransformer.ts` or reuse remark stringify |
| DEBT-04 | `documentAssembler.ts` | String-level `!\[\[note\]\]` expansion via regex. Duplicates `findNoteByFname` logic. | Cannot handle wikilink edge cases consistently; heading shift is string replacement | Already superseded by `astDocumentAssembler.ts`; deprecate after AST path default |
| DEBT-05 | `astDocumentAssembler.ts` | Uses `require("remark")` lazy-load hack to avoid ESM issues in tests. Custom `visitParents` instead of `unist-util-visit-parents`. | Non-standard, increases bundle size via lazy require, missing optimization from standard utils | Replace with static import + `unist-util-visit-parents` once ESM test issue resolved |
| DEBT-06 | `profileResolver.ts` | All reference extraction (`extractCitations`, `extractAssetRefs`, etc.) are regex scans over concatenated body strings. | Misses references inside protected blocks, counts duplicates incorrectly, cannot track provenance | Superseded by `astProfileResolver.ts`; deprecate after AST path default |

### 2.2 🟡 Medium Severity — Code Quality Debt

| ID | Location | Debt Description | Impact | Fix |
|----|----------|------------------|--------|-----|
| DEBT-07 | `escapeLatex` / `escapeLatexInlineCode` | Defined identically in `latexBackend.ts`, `astLatexTransformer.ts`, and `templateEngine.ts` | Triplicated maintenance | Extract to `docEngine/latexUtils.ts` |
| DEBT-08 | `findNoteByFname` | Duplicated (with slight drift) in `documentAssembler.ts`, `astDocumentAssembler.ts`, `profileResolver.ts`, `astProfileResolver.ts` | 4 copies of resolution logic; bug fixes must be applied 4× | Extract to `docEngine/noteResolver.ts` |
| DEBT-09 | `templateEngine.ts` `renderSkeleton` | `\{\{\s*(\w+)\s*\}\}` only supports `[A-Za-z0-9_]` variable names. No support for dots or hyphens. | User template variables like `{{document-class}}` silently fail | Expand regex to `[\w.-]+` |
| DEBT-10 | `ZoteroService.ts` `parseBibTeXEntry` | Naive regex `/([\w]+)\s*=\s*\{([^}]*)\}/g` fails on nested braces e.g. `title = {{Title}}` | Bib notes generated with corrupted fields | Replace with a brace-depth parser or use BBT `export` format |
| DEBT-11 | `ZoteroService.ts` | `getBibTeXForKeys` uses `item.bibliography` with `quickCopy: true`, which returns formatted text, not raw BibTeX. | `.bib` file content is actually formatted citation text, not valid BibTeX | Switch to `item.export` with `translator: bibtex` |
| DEBT-12 | `compileService.ts` | xmake runner checks `doc/xmake.lua` but never validates xmake installation. latexmk runner ignores exit code. | Users get silent failures or cryptic terminal errors | Add pre-flight checks for toolchain binaries |
| DEBT-13 | `astProfileResolver.ts` | `findNoteByFname` only does exact match; used for sorting `discovered` notes. Legacy resolver has suffix-match disambiguation. | Inconsistent behavior between AST and legacy paths | Unify resolver (see DEBT-08) |

### 2.3 🟢 Low Severity — Polish / Hygiene

| ID | Location | Debt Description | Impact | Fix |
|----|----------|------------------|--------|-----|
| DEBT-14 | `typstBackend.ts` | `escapeTypstInline` does not escape `_`, but `escapeTypst` does. | Potential formatting glitch in Typst output | Add `_` → `\_` to `escapeTypstInline` |
| DEBT-15 | `typstBackend.ts` / `latexBackend.ts` | `generateBibTeX` functions duplicated with identical logic. | Dual maintenance | Extract to `docEngine/bibUtils.ts` |
| DEBT-16 | `latexBackend.ts` | Inline math protection regex `/(?<!\$)\$([^$\n]+?)\$(?!\$)/g` uses lookbehind/lookahead. | May fail on Safari/older Node or complex nesting | Use AST math node detection instead |
| DEBT-17 | `commands/Zotero.ts` | `openPDFZotero` fetches attachments but does not validate MIME type; relies on `.pdf` suffix only. | Might open wrong attachment type | Check `contentType` field from BBT response |
| DEBT-18 | `docEngine/index.ts` | No re-export of `compileDocument` from `compileService.ts`; consumers import directly from subpath. | Violates barrel pattern; leaky abstraction | Add `compileDocument` to barrel |
| DEBT-19 | `sailzenBlocks.ts` (unified pkg) | `::table` directive matching requires the directive to be the **sole** content of a paragraph. If user adds trailing space/text, match fails. | UX surprise | Relax matcher to allow trailing whitespace-only children |

---

## 3. Opportunity Matrix (Next-phase work)

| Opportunity | Effort | Value | Blockers |
|-------------|--------|-------|----------|
| **Wire SailZen extensions into `astDocumentAssembler` parser** | S | 🔥 High | None — just import `sailzenCite`, `sailzenFigure`, `sailzenBlocks` plugins |
| **Build `astTypstTransformer.ts`** | M | 🔥 High | Needs wired parser first |
| **Build `astMarkdownTransformer.ts` or reuse remark stringify** | S | M | None |
| **Extract shared `noteResolver.ts`** | S | M | None |
| **Extract shared `latexUtils.ts` + `bibUtils.ts`** | S | M | None |
| **Fix BBT `.bib` export format (DEBT-11)** | S | M | Needs Zotero with BBT for verification |
| **Add xmake/latexmk pre-flight checks** | S | M | None |
| **Zotero ↔ doc profile integration** (auto-bib note creation, project `.bib` sync) | L | 🔥 High | Needs design for project-level bib lifecycle |
| **Incremental compilation / caching** | L | M | Needs file watcher + hash-based invalidation |
| **VSCode status bar for doc preview/diagnostics** | M | M | Needs diagnostics framework |

---

## 4. Quick-fix Log (Round 1)

> Round-1 goals: deduplicate, fix small bugs, improve consistency. No architectural changes.

### 4.1 Fixes Applied

1. **DEBT-07** — Extracted `escapeLatex` + `escapeLatexInlineCode` to shared `latexUtils.ts`; updated `latexBackend.ts`, `astLatexTransformer.ts`, `templateEngine.ts` to import from it.
2. **DEBT-08** — Extracted `findNoteByFname` + `extractSection` to shared `noteResolver.ts`; updated `documentAssembler.ts`, `astDocumentAssembler.ts`, `profileResolver.ts`, `astProfileResolver.ts`.
3. **DEBT-13** — `astProfileResolver.ts` now uses the unified `findNoteByFname` with suffix-match disambiguation.
4. **DEBT-14** — Added `_` escaping to `escapeTypstInline` in `typstBackend.ts`.
5. **DEBT-09** — Expanded `renderSkeleton` variable regex from `\w+` to `[\w.-]+` in `templateLoader.ts`.
6. **DEBT-18** — Added `compileDocument` re-export to `docEngine/index.ts`.
7. **DEBT-19** — Relaxed `sailzenBlocks.ts` matcher to allow trailing whitespace-only children after directive.
8. **DEBT-10 / DEBT-11** — Replaced naive BibTeX regex parser in `ZoteroService.ts` with a brace-depth parser that handles nested braces (`{{Title}}`). Switched `getBibTeXEntry` and `getBibTeXForKeys` from `item.bibliography` (formatted text) to `item.export` with `translator: "bibtex"` to emit valid raw BibTeX.

---

## 5. Test Coverage Snapshot

| Module | Test File | Status |
|--------|-----------|--------|
| AST Assembler | `astDocumentAssembler.test.ts` | ✅ Unit tests with mock parser |
| AST LaTeX | `astLatexTransformer.test.ts` | ✅ Unit tests for headings, cite, figure, mathEnv, if-format |
| Legacy Assembler | `documentAssembler.test.ts` | ⚠️ String-based tests |
| Legacy LaTeX | `latexBackend.test.ts` | ⚠️ Regex-based tests |
| Profile Resolver | `profileResolver.test.ts` | ⚠️ Legacy regex tests |
| Template Engine | `templateEngine.test.ts` | ✅ Basic tests |
| Integration | `integration.test.ts` | ⚠️ End-to-end but slow |

**Gap**: No tests for `astProfileResolver.ts`, `compileService.ts`, or `ZoteroService.ts`.

---

## 6. Appendix: Dependency Graph (docEngine internals)

```
compileService.ts
    ├── templateLoader.ts  (external template lookup)
    └── templateEngine.ts  (built-in templates + var resolution)

templateEngine.ts
    └── templateLoader.ts  (for external template rendering)

latexBackend.ts
    ├── templateEngine.ts
    ├── astLatexTransformer.ts   (when useAST=true)
    └── (would import latexUtils.ts after fix)

typstBackend.ts
    └── templateEngine.ts

markdownBackend.ts
    └── (standalone)

ExportNoteCommand.ts
    └── docEngine/index.ts

CompileDocumentCommand.ts
    ├── docEngine/index.ts
    └── docEngine/compileService.ts
```
