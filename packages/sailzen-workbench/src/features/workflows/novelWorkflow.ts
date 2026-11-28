import * as path from "path";
import * as yaml from "js-yaml";
import { parseNoteContent } from "../../core/vault/noteModel";

export interface ParsedChapterDocument {
  workId?: number;
  editionId?: number;
  nodeId?: number;
  sourceSlug: string;
  label: string;
  title: string;
  body: string;
  wordCount: number;
  charCount: number;
}

const FRONTMATTER_BLOCK_RE = /^---\r?\n([\s\S]*?)\r?\n---(?:\r?\n|$)/;

/** Count mixed CJK characters + Latin/numeric words (matches backend `_count_words_and_chars`). */
export function countChapterWords(text: string): { wordCount: number; charCount: number } {
  const cjk = (text.match(/[\u4e00-\u9fff]/g) || []).length;
  const latin = (text.match(/[A-Za-z0-9_]+/g) || []).length;
  return { wordCount: cjk + latin, charCount: text.length };
}

/**
 * Parse a local Markdown chapter file (Vault note or standalone novel repo chapter)
 * into clean sync payload fields for `PUT /api/v1/text/edition/{id}/chapter-sync`.
 */
export function parseChapterMarkdown(
  fsPath: string,
  rawMarkdown: string
): ParsedChapterDocument {
  const baseName = path.basename(fsPath, path.extname(fsPath));
  const parsed = parseNoteContent(baseName, rawMarkdown);
  const extra = parsed.frontmatter.extra;

  const numOrUndef = (v: unknown): number | undefined =>
    typeof v === "number" && Number.isFinite(v) ? v : undefined;

  const workId = numOrUndef(extra.sailzen_work_id);
  const editionId = numOrUndef(extra.sailzen_edition_id);
  const nodeId = numOrUndef(extra.sailzen_node_id);
  const sourceSlug =
    typeof extra.sailzen_source_slug === "string" && extra.sailzen_source_slug.trim()
      ? extra.sailzen_source_slug.trim()
      : baseName;

  const body = parsed.body.trim();
  // Detect first H1 heading if frontmatter title wasn't explicit
  const h1Match = body.match(/^#\s+(.+)$/m);
  const rawTitle =
    (extra.sailzen_chapter_title as string | undefined) ||
    (parsed.frontmatter.id ? parsed.frontmatter.title : h1Match?.[1]?.trim()) ||
    parsed.frontmatter.title ||
    baseName;

  // Split optional "第一章 启程" style label/title
  let label =
    typeof extra.sailzen_chapter_label === "string"
      ? extra.sailzen_chapter_label.trim()
      : "";
  let title = rawTitle.trim();
  if (!label) {
    const chMatch = title.match(/^(第[一二三四五六七八九十百千万0-9]+[章节回卷部]|Chapter\s+\d+)\s*[:：\-—\s]+(.+)$/i);
    if (chMatch) {
      label = chMatch[1].trim();
      title = chMatch[2].trim();
    }
  }

  const { wordCount, charCount } = countChapterWords(body);

  return {
    workId,
    editionId,
    nodeId,
    sourceSlug,
    label,
    title: title || baseName,
    body,
    wordCount,
    charCount,
  };
}

/**
 * Upsert `sailzen_work_id / sailzen_edition_id / sailzen_node_id / sailzen_source_slug`
 * into the Markdown file's YAML frontmatter cleanly without touching body text.
 */
export function upsertChapterSyncFrontmatter(
  rawMarkdown: string,
  meta: {
    workId: number;
    editionId: number;
    nodeId: number;
    sourceSlug: string;
  }
): string {
  const match = rawMarkdown.match(FRONTMATTER_BLOCK_RE);
  if (match) {
    let obj: Record<string, unknown> = {};
    try {
      const loaded = yaml.load(match[1]);
      if (loaded && typeof loaded === "object" && !Array.isArray(loaded)) {
        obj = loaded as Record<string, unknown>;
      }
    } catch {
      obj = {};
    }
    obj.sailzen_work_id = meta.workId;
    obj.sailzen_edition_id = meta.editionId;
    obj.sailzen_node_id = meta.nodeId;
    obj.sailzen_source_slug = meta.sourceSlug;

    const dumped = yaml.dump(obj, { lineWidth: 100, noRefs: true }).trimEnd();
    const rest = rawMarkdown.slice(match[0].length);
    return `---\n${dumped}\n---\n${rest}`;
  }

  const fmObj = {
    sailzen_work_id: meta.workId,
    sailzen_edition_id: meta.editionId,
    sailzen_node_id: meta.nodeId,
    sailzen_source_slug: meta.sourceSlug,
  };
  const dumped = yaml.dump(fmObj, { lineWidth: 100, noRefs: true }).trimEnd();
  return `---\n${dumped}\n---\n\n${rawMarkdown}`;
}
