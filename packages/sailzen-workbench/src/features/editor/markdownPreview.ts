import * as fs from "fs";
import {
  extractHeadingSection,
  NoteRecord,
  parseNoteContent,
  parseWikilinkInner,
  slugifyHeading,
} from "../../core/vault/noteModel";

const REPO_LINK_START_RE = /^repo:\/\/([a-z0-9_-]+)\/([^\s)#<>\[\]]+)(?:#L(\d+))?/i;
const MAX_EMBED_DEPTH = 2;
const MAX_EMBED_CHARS = 24_000;

export interface MarkdownPreviewResolver {
  resolveNote(target: string): NoteRecord | undefined;
  readNoteBody?(note: NoteRecord): string | undefined;
  resolveRepoPath?(slug: string): string | undefined;
}

/** Minimal structural typing for VS Code's bundled markdown-it instance (zero runtime dependency). */
export interface MarkdownItTokenLike {
  type: string;
  tag: string;
  nesting: number;
  content: string;
  attrs: Array<[string, string]> | null;
  attrSet(name: string, value: string): void;
  map?: [number, number] | null;
}

export interface MarkdownItInlineStateLike {
  src: string;
  pos: number;
  posMax: number;
  env: Record<string, unknown>;
  push(type: string, tag: string, nesting: number): MarkdownItTokenLike;
}

export interface MarkdownItBlockStateLike {
  src: string;
  bMarks: number[];
  tShift: number[];
  eMarks: number[];
  line: number;
  env: Record<string, unknown>;
  push(type: string, tag: string, nesting: number): MarkdownItTokenLike;
}

export interface MarkdownItLike {
  inline: {
    ruler: {
      before(
        beforeName: string,
        ruleName: string,
        fn: (state: MarkdownItInlineStateLike, silent: boolean) => boolean
      ): void;
      push(
        ruleName: string,
        fn: (state: MarkdownItInlineStateLike, silent: boolean) => boolean
      ): void;
    };
  };
  block: {
    ruler: {
      before(
        beforeName: string,
        ruleName: string,
        fn: (
          state: MarkdownItBlockStateLike,
          startLine: number,
          endLine: number,
          silent: boolean
        ) => boolean
      ): void;
    };
  };
  render(src: string, env?: Record<string, unknown>): string;
}

function escapeHtml(str: string): string {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function readNoteBodyDefault(note: NoteRecord): string | undefined {
  try {
    const raw = fs.readFileSync(note.fsPath, "utf8");
    return parseNoteContent(note.fname, raw, note.mtimeMs).body;
  } catch {
    return undefined;
  }
}

export function buildWikilinkHref(
  target: string,
  anchor: string | undefined,
  existingNote: NoteRecord | undefined
): string {
  if (!target && anchor) {
    return `#${slugifyHeading(anchor)}`;
  }
  const fname = existingNote ? existingNote.fname : target;
  const base = `./${encodeURIComponent(fname)}.md`;
  if (anchor) {
    return `${base}#${slugifyHeading(anchor)}`;
  }
  return base;
}

/**
 * Extend VS Code's built-in `markdown-it` engine with SailZen bidirectional links:
 * - `[[target]]`, `[[alias|target]]`, `[[target#anchor]]`, `[[#local-heading]]`
 * - `![[target]]` / `![[target#anchor]]` note transclusion cards (with cycle/depth guard)
 * - `repo://<slug>/<relPath>#L<line>` cross-machine semantic code links
 *
 * Uses standard relative `./<fname>.md` URLs so clicking works natively even under
 * VS Code's default Strict Markdown Preview security mode.
 */
export function extendMarkdownItWithSailZen<T extends MarkdownItLike>(
  md: T,
  resolver: MarkdownPreviewResolver
): T {
  const readBody = (note: NoteRecord): string | undefined =>
    resolver.readNoteBody ? resolver.readNoteBody(note) : readNoteBodyDefault(note);

  // 1. Block rule: standalone `![[target]]` or `![[target#anchor]]` note transclusion
  try {
    md.block.ruler.before(
      "paragraph",
      "sailzen_embed",
      (state, startLine, _endLine, silent) => {
        const lineStart = state.bMarks[startLine] + state.tShift[startLine];
        const lineEnd = state.eMarks[startLine];
        const lineText = state.src.slice(lineStart, lineEnd).trim();
        if (!lineText.startsWith("![[") || !lineText.endsWith("]]")) {
          return false;
        }
        const inner = lineText.slice(3, -2);
        if (inner.includes("]]") || inner.includes("[")) return false;

        const parsed = parseWikilinkInner(inner);
        if (!parsed || !parsed.target) return false;
        if (silent) return true;

        const depth = Number(state.env?.__sailzenEmbedDepth || 0);
        const embedStack = Array.isArray(state.env?.__sailzenEmbedStack)
          ? (state.env.__sailzenEmbedStack as string[])
          : [];
        const existing = resolver.resolveNote(parsed.target);
        const href = buildWikilinkHref(parsed.target, parsed.anchor, existing);
        const label =
          parsed.alias ||
          (existing ? existing.title : parsed.target) +
            (parsed.anchor ? ` § ${parsed.anchor}` : "");

        const token = state.push("html_block", "", 0);
        token.map = [startLine, startLine + 1];

        const targetKey = existing ? existing.fname.toLowerCase() : parsed.target.toLowerCase();
        if (!existing || depth >= MAX_EMBED_DEPTH || embedStack.includes(targetKey)) {
          const cls = existing
            ? "sailzen-wikilink"
            : "sailzen-wikilink sailzen-wikilink-missing";
          const titleAttr = existing
            ? `${existing.title} (${existing.fname})`
            : `${parsed.target} (not created yet)`;
          token.content = `<p><a class="${cls}" href="${escapeHtml(href)}" title="${escapeHtml(
            titleAttr
          )}">${escapeHtml(label)}</a></p>\n`;
          state.line = startLine + 1;
          return true;
        }

        let body = readBody(existing) ?? "";
        if (parsed.anchor) {
          body = extractHeadingSection(body, parsed.anchor) ?? body;
        }
        if (body.length > MAX_EMBED_CHARS) {
          body = `${body.slice(0, MAX_EMBED_CHARS)}\n\n*… (truncated in preview)*`;
        }

        const childEnv = {
          ...(state.env || {}),
          __sailzenEmbedDepth: depth + 1,
          __sailzenEmbedStack: [...embedStack, targetKey],
        };
        const renderedBody = md.render(body.trim(), childEnv);

        token.content =
          `<div class="sailzen-embed">` +
          `<div class="sailzen-embed-header">` +
          `<a class="sailzen-wikilink" href="${escapeHtml(href)}" title="${escapeHtml(
            `${existing.title} (${existing.fname})`
          )}">${escapeHtml(label)}</a>` +
          `<span class="sailzen-embed-fname">${escapeHtml(existing.fname)}</span>` +
          `</div>` +
          `<div class="sailzen-embed-body">${renderedBody}</div>` +
          `</div>\n`;

        state.line = startLine + 1;
        return true;
      }
    );
  } catch {
    // Fallback gracefully if markdown-it rule name differs
  }

  // 2. Inline rule: `[[...]]` and inline `![[...]]` wikilinks
  const wikilinkInlineRule = (state: MarkdownItInlineStateLike, silent: boolean): boolean => {
    const src = state.src;
    const pos = state.pos;
    const max = state.posMax;

    let isEmbed = false;
    let openStart = pos;
    if (pos + 4 <= max && src.startsWith("![[", pos)) {
      isEmbed = true;
      openStart = pos + 1;
    } else if (pos + 3 <= max && src.startsWith("[[", pos)) {
      openStart = pos;
    } else {
      return false;
    }

    const closeIdx = src.indexOf("]]", openStart + 2);
    if (closeIdx === -1 || closeIdx + 2 > max) return false;
    const nlIdx = src.indexOf("\n", openStart + 2);
    if (nlIdx !== -1 && nlIdx < closeIdx) return false;

    const inner = src.slice(openStart + 2, closeIdx);
    const parsed = parseWikilinkInner(inner);
    if (!parsed) return false;

    if (!silent) {
      const existing = parsed.target ? resolver.resolveNote(parsed.target) : undefined;
      const href = buildWikilinkHref(parsed.target, parsed.anchor, existing);

      let label: string;
      let className: string;
      let titleAttr: string;

      if (!parsed.target && parsed.anchor) {
        label = parsed.alias || parsed.anchor;
        className = "sailzen-wikilink sailzen-wikilink-anchor";
        titleAttr = `Jump to heading #${parsed.anchor}`;
      } else {
        const baseLabel = parsed.alias || (existing ? existing.title : parsed.target);
        label =
          !parsed.alias && parsed.anchor ? `${baseLabel} § ${parsed.anchor}` : baseLabel;
        if (isEmbed) {
          label = `↗ ${label}`;
        }
        className = existing
          ? "sailzen-wikilink"
          : "sailzen-wikilink sailzen-wikilink-missing";
        titleAttr = existing
          ? `${existing.title} (${existing.fname})`
          : `${parsed.target} (note does not exist yet)`;
      }

      const openTok = state.push("link_open", "a", 1);
      openTok.attrSet("href", href);
      openTok.attrSet("class", className);
      openTok.attrSet("title", titleAttr);
      if (parsed.target) {
        openTok.attrSet("data-wikilink-target", existing ? existing.fname : parsed.target);
      }

      const textTok = state.push("text", "", 0);
      textTok.content = label;

      state.push("link_close", "a", -1);
    }

    state.pos = closeIdx + 2;
    return true;
  };

  try {
    md.inline.ruler.before("image", "sailzen_wikilink", wikilinkInlineRule);
  } catch {
    md.inline.ruler.before("link", "sailzen_wikilink", wikilinkInlineRule);
  }

  // 3. Inline rule: `repo://<slug>/<relPath>#L<line>` semantic code links
  const repoLinkInlineRule = (state: MarkdownItInlineStateLike, silent: boolean): boolean => {
    const src = state.src;
    const pos = state.pos;
    if (!src.startsWith("repo://", pos)) return false;

    const rest = src.slice(pos, state.posMax);
    const m = rest.match(REPO_LINK_START_RE);
    if (!m) return false;

    if (!silent) {
      const slug = m[1];
      const relPath = m[2];
      const line = m[3] ? Number(m[3]) : undefined;
      const args = encodeURIComponent(JSON.stringify([{ slug, relPath, line }]));
      const bound = resolver.resolveRepoPath ? resolver.resolveRepoPath(slug) : undefined;
      const titleAttr = bound
        ? `Open ${relPath}${line ? `:${line}` : ""} in ${bound}`
        : `Repo "${slug}" (${relPath}${line ? `:${line}` : ""})`;

      const openTok = state.push("link_open", "a", 1);
      openTok.attrSet("href", `command:sailzen._openRepoLink?${args}`);
      openTok.attrSet("class", "sailzen-repolink");
      openTok.attrSet("title", titleAttr);

      const textTok = state.push("text", "", 0);
      textTok.content = `${slug}/${relPath}${line ? `:L${line}` : ""}`;

      state.push("link_close", "a", -1);
    }

    state.pos = pos + m[0].length;
    return true;
  };

  try {
    md.inline.ruler.before("link", "sailzen_repolink", repoLinkInlineRule);
  } catch {
    md.inline.ruler.push("sailzen_repolink", repoLinkInlineRule);
  }

  return md;
}
