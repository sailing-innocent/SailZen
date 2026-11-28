import * as crypto from "crypto";
import * as yaml from "js-yaml";

export interface WikilinkOccurrence {
  raw: string;
  target: string;
  alias?: string;
  anchor?: string;
  isEmbed: boolean;
  start: number;
  end: number;
  targetStart: number;
  targetEnd: number;
}

export interface ParsedWikilinkInner {
  target: string;
  alias?: string;
  anchor?: string;
  /** Offset of `target` within `inner` */
  targetOffsetInInner: number;
}

export interface HeadingInfo {
  level: number;
  text: string;
  slug: string;
  /** 0-based line number in the full raw markdown document */
  line: number;
}

export interface NoteFrontmatter {
  id: string;
  title: string;
  desc: string;
  created: number;
  updated: number;
  tags: string[];
  traitIds: string[];
  extra: Record<string, unknown>;
}

export interface NoteRecord {
  fname: string;
  fsPath: string;
  id: string;
  title: string;
  desc: string;
  created: number;
  updated: number;
  tags: string[];
  /** Deduplicated lowercase target fnames referenced by [[wikilinks]] */
  links: string[];
  mtimeMs: number;
  size: number;
}

export interface ParsedNote {
  frontmatter: NoteFrontmatter;
  body: string;
  bodyOffset: number;
  links: WikilinkOccurrence[];
}

const FRONTMATTER_RE = /^---\r?\n([\s\S]*?)\r?\n---(?:\r?\n|$)/;

/** Generate a Dendron-compatible 23-char lowercase alphanumeric ID. */
export function generateNoteId(): string {
  const alphabet = "0123456789abcdefghijklmnopqrstuvwxyz";
  const bytes = crypto.randomBytes(23);
  let out = "";
  for (let i = 0; i < 23; i++) {
    out += alphabet[bytes[i] % alphabet.length];
  }
  return out;
}

/** Derive human-friendly title from the last dot segment of fname. */
export function deriveTitleFromFname(fname: string): string {
  const parts = fname.split(".");
  const last = parts[parts.length - 1] || fname;
  return last
    .split(/[-_]+/)
    .filter(Boolean)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

/** Normalize tags field from YAML (string or array). */
function normalizeStringList(val: unknown): string[] {
  if (Array.isArray(val)) {
    return val.map((v) => String(v).trim()).filter(Boolean);
  }
  if (typeof val === "string" && val.trim()) {
    return [val.trim()];
  }
  return [];
}

/**
 * GitHub / VS Code native Markdown Preview compatible heading slugifier.
 * Preserves Unicode letters/digits (including CJK) and converts whitespace to hyphens.
 */
export function slugifyHeading(heading: string): string {
  return heading
    .trim()
    .toLowerCase()
    .replace(/[^\p{L}\p{N}\s_-]/gu, "")
    .replace(/\s+/g, "-");
}

/**
 * Parse the inner text of `[[...]]` or `![[...]]`:
 * supports `target`, `alias|target`, `target#anchor`, `alias|target#anchor`,
 * `#local-heading`, `alias|#local-heading`, and `dendron://vault/target` / `sail://vault/target`.
 */
export function parseWikilinkInner(inner: string): ParsedWikilinkInner | null {
  if (!inner || !inner.trim() || inner.includes("[")) return null;

  const pipeIdx = inner.indexOf("|");
  let alias: string | undefined;
  let targetPart: string;
  let targetPartStart: number;

  if (pipeIdx !== -1) {
    alias = inner.slice(0, pipeIdx).trim() || undefined;
    targetPart = inner.slice(pipeIdx + 1);
    targetPartStart = pipeIdx + 1;
  } else {
    targetPart = inner;
    targetPartStart = 0;
  }

  const leadingWs = targetPart.length - targetPart.trimStart().length;
  targetPartStart += leadingWs;
  targetPart = targetPart.trim();
  if (!targetPart) return null;

  const hashIdx = targetPart.indexOf("#");
  let target: string;
  let anchor: string | undefined;
  if (hashIdx !== -1) {
    target = targetPart.slice(0, hashIdx).trim();
    anchor = targetPart.slice(hashIdx + 1).trim() || undefined;
  } else {
    target = targetPart;
  }

  let targetOffsetInInner = targetPartStart;
  const vaultPrefixMatch = target.match(/^(?:dendron|sail):\/\/[^/]+\//i);
  if (vaultPrefixMatch) {
    targetOffsetInInner += vaultPrefixMatch[0].length;
    target = target.slice(vaultPrefixMatch[0].length);
  }

  if (!target && !anchor) return null;

  return {
    target,
    alias,
    anchor,
    targetOffsetInInner,
  };
}

/**
 * Extract Markdown ATX headings (`#` .. `######`) while skipping YAML frontmatter and fenced code blocks.
 */
export function extractHeadings(rawMarkdown: string): HeadingInfo[] {
  const lines = rawMarkdown.split(/\r?\n/);
  const headings: HeadingInfo[] = [];
  let i = 0;

  // Skip leading YAML frontmatter if present
  if (lines.length > 0 && lines[0].trim() === "---") {
    for (let j = 1; j < lines.length; j++) {
      if (lines[j].trim() === "---") {
        i = j + 1;
        break;
      }
    }
  }

  let inFence = false;
  let fenceChar = "";
  let fenceLen = 0;

  for (; i < lines.length; i++) {
    const line = lines[i];
    const trimmed = line.trimStart();
    const fenceMatch = trimmed.match(/^(`{3,}|~{3,})/);
    if (fenceMatch) {
      const ch = fenceMatch[1][0];
      const len = fenceMatch[1].length;
      if (!inFence) {
        inFence = true;
        fenceChar = ch;
        fenceLen = len;
      } else if (ch === fenceChar && len >= fenceLen) {
        inFence = false;
      }
      continue;
    }
    if (inFence) continue;

    const hMatch = line.match(/^(#{1,6})\s+(.+?)\s*#*\s*$/);
    if (hMatch) {
      const text = hMatch[2].trim();
      headings.push({
        level: hMatch[1].length,
        text,
        slug: slugifyHeading(text),
        line: i,
      });
    }
  }

  return headings;
}

/** Find 0-based line number for a heading anchor in raw markdown. */
export function findHeadingLine(rawMarkdown: string, anchor: string): number | undefined {
  const qRaw = anchor.trim().toLowerCase();
  const qSlug = slugifyHeading(anchor);
  if (!qRaw && !qSlug) return undefined;

  const headings = extractHeadings(rawMarkdown);
  const exact = headings.find(
    (h) => h.slug === qSlug || h.text.toLowerCase() === qRaw
  );
  if (exact) return exact.line;

  const partial = headings.find(
    (h) => h.slug.includes(qSlug) || h.text.toLowerCase().includes(qRaw)
  );
  return partial?.line;
}

/** Extract a specific heading section from markdown body (until next heading of same or higher level). */
export function extractHeadingSection(body: string, anchor: string): string | undefined {
  const headings = extractHeadings(body);
  const qRaw = anchor.trim().toLowerCase();
  const qSlug = slugifyHeading(anchor);
  const idx = headings.findIndex(
    (h) => h.slug === qSlug || h.text.toLowerCase() === qRaw || h.text.toLowerCase().includes(qRaw)
  );
  if (idx === -1) return undefined;

  const start = headings[idx];
  const lines = body.split(/\r?\n/);
  let endLine = lines.length;
  for (let i = idx + 1; i < headings.length; i++) {
    if (headings[i].level <= start.level) {
      endLine = headings[i].line;
      break;
    }
  }
  return lines.slice(start.line, endLine).join("\n").trim();
}

/**
 * Extract [[wikilink]] occurrences while ignoring fenced code blocks and inline code.
 * Offsets are relative to `content` (pass `baseOffset` to convert to full-document offsets).
 */
export function extractWikilinks(
  content: string,
  baseOffset = 0
): WikilinkOccurrence[] {
  const results: WikilinkOccurrence[] = [];
  const len = content.length;
  let i = 0;
  let inFence = false;
  let fenceChar = "";
  let fenceLen = 0;
  let inInlineCode = false;
  let inlineTicks = 0;

  while (i < len) {
    // Check start-of-line fenced code blocks (``` or ~~~)
    const atLineStart = i === 0 || content[i - 1] === "\n";
    if (atLineStart && !inInlineCode) {
      let j = i;
      while (j < len && (content[j] === " " || content[j] === "\t")) j++;
      if (j < len && (content[j] === "`" || content[j] === "~")) {
        const ch = content[j];
        let k = j;
        while (k < len && content[k] === ch) k++;
        const count = k - j;
        if (count >= 3) {
          if (!inFence) {
            inFence = true;
            fenceChar = ch;
            fenceLen = count;
          } else if (ch === fenceChar && count >= fenceLen) {
            inFence = false;
          }
          // Skip rest of fence line
          const nl = content.indexOf("\n", k);
          i = nl === -1 ? len : nl + 1;
          continue;
        }
      }
    }

    if (inFence) {
      const nl = content.indexOf("\n", i);
      i = nl === -1 ? len : nl + 1;
      continue;
    }

    // Inline code spans
    if (content[i] === "`") {
      let k = i;
      while (k < len && content[k] === "`") k++;
      const count = k - i;
      if (!inInlineCode) {
        inInlineCode = true;
        inlineTicks = count;
      } else if (count === inlineTicks) {
        inInlineCode = false;
      }
      i = k;
      continue;
    }

    if (inInlineCode) {
      if (content[i] === "\n") {
        // Recover cleanly from unclosed inline backtick at newline
        inInlineCode = false;
      }
      i++;
      continue;
    }

    // Check [[ or ![[
    if (content[i] === "[" && i + 1 < len && content[i + 1] === "[") {
      const isEmbed = i > 0 && content[i - 1] === "!";
      const start = isEmbed ? i - 1 : i;
      const closeIdx = content.indexOf("]]", i + 2);
      const newlineIdx = content.indexOf("\n", i + 2);
      if (closeIdx !== -1 && (newlineIdx === -1 || closeIdx < newlineIdx)) {
        const inner = content.slice(i + 2, closeIdx);
        const innerStart = i + 2;
        const parsed = parseWikilinkInner(inner);
        if (parsed) {
          const targetStartOffset = innerStart + parsed.targetOffsetInInner;
          results.push({
            raw: content.slice(start, closeIdx + 2),
            target: parsed.target,
            alias: parsed.alias,
            anchor: parsed.anchor,
            isEmbed,
            start: baseOffset + start,
            end: baseOffset + closeIdx + 2,
            targetStart: baseOffset + targetStartOffset,
            targetEnd: baseOffset + targetStartOffset + parsed.target.length,
          });
        }
        i = closeIdx + 2;
        continue;
      }
    }

    i++;
  }

  return results;
}

/** Parse a Markdown file into Dendron-compatible frontmatter, body, and wikilinks. */
export function parseNoteContent(
  fname: string,
  raw: string,
  mtimeMs = Date.now()
): ParsedNote {
  let fmData: Record<string, unknown> = {};
  let body = raw;
  let bodyOffset = 0;

  const match = raw.match(FRONTMATTER_RE);
  if (match) {
    bodyOffset = match[0].length;
    body = raw.slice(bodyOffset);
    try {
      const parsed = yaml.load(match[1]);
      if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
        fmData = parsed as Record<string, unknown>;
      }
    } catch {
      // Malformed YAML in an old note: fall back safely without throwing
      fmData = {};
    }
  }

  const id = typeof fmData.id === "string" && fmData.id.trim() ? fmData.id.trim() : "";
  const title =
    typeof fmData.title === "string" && fmData.title.trim()
      ? fmData.title.trim()
      : deriveTitleFromFname(fname);
  const desc = typeof fmData.desc === "string" ? fmData.desc : "";
  const created =
    typeof fmData.created === "number" ? fmData.created : Math.floor(mtimeMs);
  const updated =
    typeof fmData.updated === "number" ? fmData.updated : Math.floor(mtimeMs);
  const tags = normalizeStringList(fmData.tags);
  const traitIds = normalizeStringList(fmData.traitIds);

  const extra: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(fmData)) {
    if (!["id", "title", "desc", "created", "updated", "tags", "traitIds"].includes(k)) {
      extra[k] = v;
    }
  }

  const links = extractWikilinks(body, bodyOffset);

  return {
    frontmatter: { id, title, desc, created, updated, tags, traitIds, extra },
    body,
    bodyOffset,
    links,
  };
}

/** Build a compact NoteRecord from raw markdown content + file stats. */
export function buildNoteRecord(
  fname: string,
  fsPath: string,
  raw: string,
  mtimeMs: number,
  size: number
): NoteRecord {
  const parsed = parseNoteContent(fname, raw, mtimeMs);
  const uniqueLinks = Array.from(
    new Set(
      parsed.links
        .filter((l) => l.target.length > 0)
        .map((l) => l.target.toLowerCase())
    )
  );
  return {
    fname,
    fsPath,
    id: parsed.frontmatter.id,
    title: parsed.frontmatter.title,
    desc: parsed.frontmatter.desc,
    created: parsed.frontmatter.created,
    updated: parsed.frontmatter.updated,
    tags: parsed.frontmatter.tags,
    links: uniqueLinks,
    mtimeMs,
    size,
  };
}

/** Serialize a brand-new Dendron-compatible note file. */
export function serializeNewNote(opts: {
  fname: string;
  title?: string;
  desc?: string;
  body?: string;
  traitIds?: string[];
  tags?: string[];
  now?: number;
}): string {
  const now = opts.now ?? Date.now();
  const fmObj: Record<string, unknown> = {
    id: generateNoteId(),
    title: opts.title ?? deriveTitleFromFname(opts.fname),
    desc: opts.desc ?? "",
    updated: now,
    created: now,
  };
  if (opts.tags && opts.tags.length > 0) {
    fmObj.tags = opts.tags;
  }
  if (opts.traitIds && opts.traitIds.length > 0) {
    fmObj.traitIds = opts.traitIds;
  }
  const fmYaml = yaml.dump(fmObj, { lineWidth: 100, noRefs: true }).trimEnd();
  const body = opts.body ? opts.body.replace(/^\r?\n/, "") : "";
  return `---\n${fmYaml}\n---\n\n${body}${body.endsWith("\n") || !body ? "" : "\n"}`;
}
