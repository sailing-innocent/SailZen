import {
  AssembledDocument,
  DocProfile,
  extractDocFrontmatter,
  NoteProps,
  NotePropsByIdDict,
} from "@saili/common-all";
import { findNoteByFname, extractSection } from "./noteResolver";

const NOTE_REF_REGEX = /!\[\[([^\]]+)\]\]/g;
const HEADING_REGEX = /^(#{1,6})\s+/gm;

/**
 * Assemble a complete document by recursively expanding note references.
 *
 * @param profile - Resolved document profile
 * @param notesById - All notes in the engine
 * @returns Assembled document with body and metadata
 */
export function assembleDocument(
  profile: DocProfile,
  notesById: NotePropsByIdDict
): AssembledDocument {
  const rootNote = Object.values(notesById).find(
    (n) => n.id === profile.rootNoteId
  );
  if (!rootNote) {
    // eslint-disable-next-line no-console
    console.error("[documentAssembler] Root note not found:", {
      rootNoteId: profile.rootNoteId,
      availableIds: Object.keys(notesById),
      availableCount: Object.keys(notesById).length,
    });
    throw new Error(`Root note ${profile.rootNoteId} not found`);
  }

  const includedNotes = new Set<string>();
  const unresolvedRefs: string[] = [];

  // Start with root note body, depth offset = 0
  let body = expandNoteRefs(
    rootNote.body,
    notesById,
    0,
    includedNotes,
    unresolvedRefs,
    rootNote.fname
  );

  // Append explicitly included notes that were NOT already included via note refs.
  // profile.includes fnames come from resolveProfile and are always full fnames.
  for (const fname of profile.includes) {
    const note = findNoteByFname(fname, notesById);
    if (!note) {
      unresolvedRefs.push(fname);
      continue;
    }
    if (includedNotes.has(note.id)) {
      continue;
    }
    const noteBody = expandNoteRefs(
      note.body,
      notesById,
      0,
      includedNotes,
      unresolvedRefs,
      note.fname
    );
    body += "\n\n" + noteBody;
    includedNotes.add(note.id);
  }

  // Append discovered compose notes that were NOT already included via note refs.
  // profile.discovered fnames come from resolveProfile and are always full fnames.
  for (const fname of profile.discovered) {
    const note = findNoteByFname(fname, notesById);
    if (!note) {
      unresolvedRefs.push(fname);
      continue;
    }

    // Skip if already included via ![[note.ref]] expansion
    if (includedNotes.has(note.id)) {
      continue;
    }

    const noteBody = expandNoteRefs(
      note.body,
      notesById,
      0,
      includedNotes,
      unresolvedRefs,
      note.fname
    );
    body += "\n\n" + noteBody;
    includedNotes.add(note.id);
  }

  return {
    body,
    headingOffsets: {}, // TODO: track per-note heading offsets
    includedNotes: Array.from(includedNotes),
    unresolvedRefs,
  };
}

/**
 * Recursively expand ![[note.ref]] patterns in markdown text.
 *
 * Supported Sail embed-ref syntax variants:
 *   ![[note.fname]]
 *   ![[note.fname#anchor]]
 *   ![[Alias|note.fname]]
 *   ![[Alias|note.fname#anchor]]
 *
 * @param text - Markdown body text
 * @param notesById - Engine note dictionary
 * @param depthOffset - How many levels to shift headings down
 * @param visited - Set of already-included note IDs (prevents cycles)
 * @param unresolved - Accumulator for unresolved references
 * @param contextFname - The fname of the note being expanded (used for suffix-match disambiguation)
 * @returns Expanded markdown text
 */
function expandNoteRefs(
  text: string,
  notesById: NotePropsByIdDict,
  depthOffset: number,
  visited: Set<string>,
  unresolved: string[],
  contextFname?: string
): string {
  if (!text) return "";

  // Adjust heading depths
  let adjusted = text;
  if (depthOffset > 0) {
    adjusted = text.replace(HEADING_REGEX, (match, hashes) => {
      const newDepth = Math.min(hashes.length + depthOffset, 6);
      return "#".repeat(newDepth) + " ";
    });
  }

  // Replace note refs
  const result = adjusted.replace(NOTE_REF_REGEX, (_match, ref) => {
    // Step 1: strip alias prefix — "Alias|note.fname#anchor" → "note.fname#anchor"
    const refWithoutAlias = ref.includes("|") ? ref.split("|").slice(1).join("|") : ref;
    // Step 2: strip anchor — "note.fname#anchor" → fname="note.fname", anchor="anchor"
    const fname = refWithoutAlias.split("#")[0].trim();
    const anchor = refWithoutAlias.includes("#")
      ? refWithoutAlias.split("#").slice(1).join("#")
      : undefined;

    const note = findNoteByFname(fname, notesById, contextFname);
    if (!note) {
      unresolved.push(fname);
      return `\n\n> **Unresolved reference**: [[${fname}]]\n\n`;
    }

    if (visited.has(note.id)) {
      return `\n\n> **Note already included**: [[${fname}]]\n\n`;
    }
    visited.add(note.id);

    let noteBody = note.body;

    // If anchor is specified, extract only that section
    if (anchor) {
      noteBody = extractSection(noteBody, anchor);
    }

    // Determine whether to shift headings down.
    // By default, embedded compose notes have their headings shifted down
    // by one level. This can be disabled via doc.shiftHeadings: false.
    const noteDoc = extractDocFrontmatter(note.custom);
    const shouldShift = noteDoc?.shiftHeadings !== false;
    const newDepthOffset = shouldShift ? depthOffset + 1 : depthOffset;

    // Recursively expand with (optionally) increased heading depth.
    // Compose notes embedded via ![[...]] have their own internal heading
    // structure. We increase depthOffset so that a # Heading inside a
    // referenced note becomes ## Heading when placed inside a parent that
    // already has its own top-level headings.
    return expandNoteRefs(
      noteBody,
      notesById,
      newDepthOffset,
      visited,
      unresolved,
      note.fname  // pass resolved note fname as context for nested refs
    );
  });

  return result;
}


