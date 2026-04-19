import {
  AssembledDocument,
  DocProfile,
  extractDocFrontmatter,
  NoteProps,
  NotePropsByIdDict,
} from "@saili/common-all";

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
    unresolvedRefs
  );

  // Append discovered compose notes in order
  for (const fname of profile.discovered) {
    const note = findNoteByFname(fname, notesById);
    if (note) {
      const noteBody = expandNoteRefs(
        note.body,
        notesById,
        0,
        includedNotes,
        unresolvedRefs
      );
      body += "\n\n" + noteBody;
      includedNotes.add(note.id);
    } else {
      unresolvedRefs.push(fname);
    }
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
 * @param text - Markdown body text
 * @param notesById - Engine note dictionary
 * @param depthOffset - How many levels to shift headings down
 * @param visited - Set of already-included note IDs (prevents cycles)
 * @param unresolved - Accumulator for unresolved references
 * @returns Expanded markdown text
 */
function expandNoteRefs(
  text: string,
  notesById: NotePropsByIdDict,
  depthOffset: number,
  visited: Set<string>,
  unresolved: string[]
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
  const result = adjusted.replace(NOTE_REF_REGEX, (match, ref) => {
    const fname = ref.split("#")[0].trim(); // Strip anchor
    const anchor = ref.includes("#")
      ? ref.split("#").slice(1).join("#")
      : undefined;

    const note = findNoteByFname(fname, notesById);
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

    // Recursively expand with increased heading depth
    return expandNoteRefs(
      noteBody,
      notesById,
      depthOffset + 1,
      visited,
      unresolved
    );
  });

  return result;
}

/**
 * Find a note by its fname in the note dictionary.
 */
function findNoteByFname(
  fname: string,
  notesById: NotePropsByIdDict
): NoteProps | undefined {
  for (const note of Object.values(notesById)) {
    if (note.fname === fname) {
      return note;
    }
  }
  return undefined;
}

/**
 * Extract a section from markdown body by heading anchor.
 * Returns content from the matching heading to the next heading of same or higher level.
 */
function extractSection(body: string, anchor: string): string {
  const lines = body.split("\n");
  const anchorLower = anchor.toLowerCase().replace(/\s+/g, "-");

  let startIdx = -1;
  let startLevel = 0;

  // Find the heading matching the anchor
  for (let i = 0; i < lines.length; i++) {
    const match = lines[i].match(/^(#{1,6})\s+(.+)$/);
    if (match) {
      const headingText = match[2].trim().toLowerCase().replace(/\s+/g, "-");
      if (headingText === anchorLower) {
        startIdx = i;
        startLevel = match[1].length;
        break;
      }
    }
  }

  if (startIdx === -1) return body; // Anchor not found, return full body

  // Find the end of the section
  let endIdx = lines.length;
  for (let i = startIdx + 1; i < lines.length; i++) {
    const match = lines[i].match(/^(#{1,6})\s+/);
    if (match && match[1].length <= startLevel) {
      endIdx = i;
      break;
    }
  }

  return lines.slice(startIdx, endIdx).join("\n");
}
