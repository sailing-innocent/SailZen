# Unified Package Functional Status

> Package: `@saili/unified` v0.3.7
> Last updated: 2026-02

## Overview

The `unified` package provides remark/rehype plugins that extend standard Markdown with Dendron-specific and SailZen-specific syntax. It sits between raw markdown text and rendered HTML, handling parsing, AST transformation, and compilation for multiple output destinations.

## Architecture

```
Raw Markdown
    |
    v
[remark-parse] + custom tokenizers  -->  MDAST (custom nodes)
    |
    v
[remark plugins] transform AST
    |
    v
[remark-rehype] + [rehype plugins]  -->  HAST (HTML AST)
    |
    v
[rehype-stringify]                  -->  HTML / Markdown / Other
```

**Key processor factories:**
- `MDUtilsV5.procRehypeFull()` — Server-side full pipeline (HTML output)
- `MDUtilsV5Web.procRehypeWeb()` — Browser-compatible pipeline
- `MDUtilsV5.procRemarkFull()` — Internal remark-only pipeline (used by noteRefsV2)

## Custom AST Node Types

Defined in `src/types.ts` as `DendronASTTypes`:

| Type String | TypeScript Interface | Purpose |
|-------------|---------------------|---------|
| `wikiLink` | `WikiLinkNoteV4` | `[[target]]`, `[[alias\|target]]` cross-references |
| `refLinkV2` | `NoteRefNoteV4` | `![[note-ref]]` transclusion |
| `blockAnchor` | `BlockAnchor` | `^anchor` block references |
| `hashtag` | `HashTag` | `#tag` topic tags |
| `zdoctag` | `ZDocTag` | `\cite{key}` zdoc citations |
| `extendedImage` | `ExtendedImage` | `![alt](url){props}` images with YAML props |
| `sailzenCite` | `SailZenCite` | `::cite[key1, key2]` inline citations |
| `sailzenFigure` | `SailZenFigure` | `::figure[caption](src){opts}` figures |
| `sailzenTable` | — | Table directive (registered type, implementation TBD) |
| `sailzenMathEnv` | — | Math environment (registered type, implementation TBD) |
| `sailzenAlgorithm` | — | Algorithm block (registered type, implementation TBD) |
| `sailzenIfFormat` | — | Conditional format (registered type, implementation TBD) |

## Plugin Inventory

### Remark Plugins (`src/remark/`)

| Plugin | Syntax | Status | Tests | Notes |
|--------|--------|--------|-------|-------|
| `wikiLinks` | `[[target]]` | ✅ Active | ✅ | Dual implementation: legacy tokenizer + micromark extension |
| `hashtag` | `#tag` | ✅ Active | ✅ | Config-gated (`enableHashTags`) |
| `zdocTags` | `\cite{key}` | ✅ Active | ✅ | Config-gated (`enableZDocTags`) |
| `blockAnchors` | `^anchor` | ✅ Active | ✅ | **Bug in `matchBlockAnchor`**: checks `match.length == 1` but regex always produces `length >= 2`, so function always returns `undefined` |
| `noteRefsV2` | `![[ref]]` | ✅ Active | ❌ | Most complex plugin: transclusion, anchor ranges, wildcards, pretty refs, `MAX_REF_LVL = 3` nesting limit |
| `extendedImage` | `![alt](url){props}` | ✅ Active | ❌ | Parses YAML props via `js-yaml`; falls back to regular image on parse failure |
| `sailzenCite` | `::cite[keys]` | ✅ Active | ❌ | Splits keys on comma; renders `<sup>[keys]</sup>` for HTML |
| `sailzenFigure` | `::figure[cap](src){opts}` | ✅ Active | ❌ | Parses `key="value"` / `key=value` options |
| `backlinks` | — | ✅ Active | ❌ | Injects backlink sections into notes |
| `hierarchies` | — | ✅ Active | ❌ | Handles note hierarchy metadata |
| `dendronPub` | — | ✅ Active | ❌ | Publication-ready transformations |
| `dendronPreview` | — | ✅ Active | ❌ | Preview-specific transformations |
| `transformLinks` | — | ✅ Active | ❌ | Link transformation utilities |
| `abbr` | — | ✅ Active | ❌ | Abbreviation support |
| `publishSite` | — | ✅ Active | ❌ | Site publication logic |

### Rehype Plugins (`src/rehype/`)

| Plugin | Purpose | Status | Tests |
|--------|---------|--------|-------|
| `wrap` | Wrap HAST elements matching selector | ✅ Active | ✅ |
| *(others)* | Various HTML transformations | ✅ Active | ❌ |

### Decoration Modules (`src/decorations/`)

All 10 modules are **untested**. They provide editor decorations (VSCode) rather than rendering:

| Module | Decorates |
|--------|-----------|
| `decorations.ts` | Dispatcher/router |
| `wikilinks.ts` | Wiki link underlines/highlights |
| `hashTags.ts` | Hashtag highlights |
| `blockAnchors.ts` | Block anchor indicators |
| `zdocTags.ts` | ZDoc tag highlights |
| `references.ts` | Reference indicators |
| `taskNotes.ts` | Task note markers |
| `frontmatter.ts` | Frontmatter folding |
| `diagnostics.ts` | Error/warning squiggles |
| `utils.ts` | Shared decoration utilities |

## Compiler Destinations

All custom plugins switch on `DendronASTDest`:

| Destination | Purpose |
|-------------|---------|
| `MD_DENDRON` | Round-trip markdown (preserve custom syntax) |
| `MD_REGULAR` | Standard markdown (strip custom syntax) |
| `MD_ENHANCED_PREVIEW` | Enhanced markdown preview |
| `HTML` | Full HTML rendering |
| `DOC_EXPORT` | Document export backend placeholder |
| `DOC_PREVIEW` | Document preview mode |

## External Plugins Integrated

| Plugin | Purpose |
|--------|---------|
| `remark-gfm` | GitHub Flavored Markdown (tables, strikethrough, etc.) |
| `remark-math` | `$...$` and `$$...$$` math syntax |
| `rehype-katex` | KaTeX math rendering |
| `rehype-prism` | Syntax highlighting via Prism |
| `remark-frontmatter` | YAML frontmatter parsing |
| `rehype-slug` | Auto-generate heading IDs |
| `rehype-autolink-headings` | Auto-link headings |
| `rehype-raw` | Parse raw HTML in markdown |

## Test Coverage Summary

### Tested Plugins
- `hashtag` — regex, utils, full processor
- `wikiLinks` — regex, utils, full processor
- `zdocTags` — regex, utils, full processor
- `blockAnchors` — regex, utils, full processor *(new)*
- `wrap` (rehype) — selector wrapping

### Untested Plugins (Priority Order)
1. **High**: `noteRefsV2` — complex transclusion logic, anchor slicing, wildcard resolution
2. **Medium**: `extendedImage`, `sailzenCite`, `sailzenFigure` — standard tokenizer/compiler pattern
3. **Medium**: `backlinks`, `hierarchies` — metadata injection
4. **Low**: `dendronPub`, `dendronPreview`, `transformLinks`, `abbr`, `publishSite`
5. **Low**: All `decorations/` modules (VSCode-specific, harder to test headlessly)
