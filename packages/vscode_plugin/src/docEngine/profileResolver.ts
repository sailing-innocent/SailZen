import {
  DocExportConfig,
  DocFrontmatter,
  DocMeta,
  DocProfile,
  DocRole,
  extractDocFrontmatter,
  NoteProps,
  NotePropsByIdDict,
} from "@saili/common-all";
import _ from "lodash";

/**
 * Resolve a DocProfile from a root note and the engine's note dictionary.
 *
 * @param rootNote - The standalone note that defines the document project
 * @param notesById - All notes in the engine (NotePropsByIdDict)
 * @returns Resolved DocProfile
 */
export function resolveProfile(
  rootNote: NoteProps,
  notesById: NotePropsByIdDict
): DocProfile {
  const docFm = extractDocFrontmatter(rootNote.custom);

  const exports: DocExportConfig[] = docFm?.exports || [
    { format: "latex", template: "article" },
  ];

  const meta: DocMeta = docFm?.meta || {
    authors: rootNote.custom?.authors,
    keywords: Array.isArray(rootNote.tags)
      ? rootNote.tags
      : rootNote.tags
        ? [rootNote.tags]
        : undefined,
  };

  const projectName = docFm?.project;
  const includes: string[] = docFm?.includes || [];

  // Auto-discover compose notes in the same project
  const discovered: string[] = [];
  if (projectName) {
    for (const note of Object.values(notesById)) {
      if (note.id === rootNote.id) continue;
      const noteDoc = extractDocFrontmatter(note.custom);
      if (
        noteDoc?.role === "compose" &&
        noteDoc?.project === projectName
      ) {
        discovered.push(note.fname);
      }
    }
    // Sort by order, then by fname
    discovered.sort((a, b) => {
      const noteA = notesById[Object.keys(notesById).find(id => notesById[id].fname === a) || ""];
      const noteB = notesById[Object.keys(notesById).find(id => notesById[id].fname === b) || ""];
      const orderA = extractDocFrontmatter(noteA?.custom)?.order ?? Infinity;
      const orderB = extractDocFrontmatter(noteB?.custom)?.order ?? Infinity;
      return orderA - orderB || a.localeCompare(b);
    });
  }

  // Collect citations from root note body (simple regex extraction)
  const citations = extractCitations(rootNote.body);

  // Collect asset references (simple regex extraction)
  const assets = extractAssetRefs(rootNote.body);

  return {
    rootNoteId: rootNote.id,
    rootNoteFname: rootNote.fname,
    vaultName: rootNote.vault?.name,
    exports,
    meta,
    includes,
    discovered,
    citations,
    assets,
  };
}

/**
 * Extract ::cite[keys] citations from markdown text
 */
export function extractCitations(body: string): string[] {
  const citeRegex = /::cite\[([^\]]+)\]/g;
  const keys: string[] = [];
  let match;
  while ((match = citeRegex.exec(body)) !== null) {
    const raw = match[1];
    const parts = raw.split(/,\s*/).map((s) => s.trim()).filter(Boolean);
    keys.push(...parts);
  }
  return _.uniq(keys);
}

/**
 * Extract ::figure references from markdown text
 */
export function extractAssetRefs(body: string): string[] {
  const figRegex = /::figure\[[^\]]*\]\s*\(([^)]+)\)/g;
  const refs: string[] = [];
  let match;
  while ((match = figRegex.exec(body)) !== null) {
    refs.push(match[1].trim());
  }
  return _.uniq(refs);
}
