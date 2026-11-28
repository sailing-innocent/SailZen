/**
 * @file noteResolver.ts
 * @brief Shared note resolution utilities for SailZen Doc Engine
 * @description Consolidates findNoteByFname and extractSection to avoid
 *   duplication across documentAssembler, astDocumentAssembler, profileResolver,
 *   and astProfileResolver.
 */

import { NoteProps, NotePropsByIdDict } from "@saili/common-all";

/**
 * Find a note by its fname in the note dictionary.
 *
 * Resolution order:
 *  1. Exact match: note.fname === fname
 *  2. Suffix match: note.fname ends with ".<fname>" (handles short refs like "overview"
 *     matching "project.myproject.overview")
 *
 * When multiple suffix matches exist, the one sharing the longest common prefix with
 * contextFname wins (sibling preference). Ties broken by shortest fname.
 */
export function findNoteByFname(
  fname: string,
  notesById: NotePropsByIdDict,
  contextFname?: string
): NoteProps | undefined {
  // 1. Exact match
  for (const note of Object.values(notesById)) {
    if (note.fname === fname) {
      return note;
    }
  }

  // 2. Suffix match – collect all candidates that end with ".<fname>"
  const suffix = "." + fname;
  const candidates: NoteProps[] = [];
  for (const note of Object.values(notesById)) {
    if (note.fname.endsWith(suffix)) {
      candidates.push(note);
    }
  }

  if (candidates.length === 0) {
    return undefined;
  }

  if (candidates.length === 1) {
    return candidates[0];
  }

  // Multiple candidates – prefer the one sharing the longest common prefix with contextFname,
  // then fall back to the shortest fname (closest to root).
  if (contextFname) {
    const contextParts = contextFname.split(".");
    let bestNote: NoteProps = candidates[0];
    let bestScore = -1;
    for (const c of candidates) {
      const parts = c.fname.split(".");
      let shared = 0;
      for (let i = 0; i < Math.min(contextParts.length, parts.length - 1); i++) {
        if (contextParts[i] === parts[i]) shared++;
        else break;
      }
      if (
        shared > bestScore ||
        (shared === bestScore && c.fname.length < bestNote.fname.length)
      ) {
        bestScore = shared;
        bestNote = c;
      }
    }
    return bestNote;
  }

  // No context – pick shortest fname
  candidates.sort((a, b) => a.fname.length - b.fname.length);
  return candidates[0];
}

/**
 * Extract a section from markdown body by heading anchor.
 * Returns content from the matching heading to the next heading of same or higher level.
 */
export function extractSection(body: string, anchor: string): string {
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
