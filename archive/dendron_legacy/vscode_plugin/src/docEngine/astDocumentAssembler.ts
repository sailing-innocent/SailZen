/**
 * @file astDocumentAssembler.ts
 * @brief AST-level document assembly for SailZen Doc Engine
 * @description Replaces string-based note-ref expansion with MDAST-level
 *   transclusion. Parses each note into an AST, recursively replaces
 *   refLinkV2 nodes with referenced note ASTs, and adjusts heading depths.
 */

import {
  AssembledDocument,
  DocProfile,
  extractDocFrontmatter,
  NoteProps,
  NotePropsByIdDict,
} from "@saili/common-all";
import { findNoteByFname, extractSection } from "./noteResolver";
import type { Node, Parent, Root, Heading } from "mdast";

const REF_LINK_V2 = "refLinkV2";

export type NoteParser = (body: string) => Root;

let defaultParser: NoteParser | undefined;

function getDefaultParser(): NoteParser {
  if (!defaultParser) {
    // Lazy-load remark to avoid ESM issues during test module loading
    const { remark } = require("remark");
    const remarkParse = require("remark-parse").default;
    defaultParser = (body: string) =>
      remark().use(remarkParse, { gfm: true }).parse(body) as Root;
  }
  return defaultParser;
}

// ============================================================================
// Public API
// ============================================================================

export function assembleDocumentAST(
  profile: DocProfile,
  notesById: NotePropsByIdDict,
  parser?: NoteParser
): { ast: Root; includedNotes: string[]; unresolvedRefs: string[] } {
  const parse = parser || getDefaultParser();
  const rootNote = Object.values(notesById).find(
    (n) => n.id === profile.rootNoteId
  );
  if (!rootNote) {
    throw new Error(`Root note ${profile.rootNoteId} not found`);
  }

  const includedNotes = new Set<string>();
  const unresolvedRefs: string[] = [];

  // Parse root note into AST and expand refs
  const rootAST = parse(rootNote.body);
  expandRefsInAST(rootAST, notesById, 0, includedNotes, unresolvedRefs, rootNote.fname, parse);
  includedNotes.add(rootNote.id);

  // Append explicitly included notes
  for (const fname of profile.includes) {
    const note = findNoteByFname(fname, notesById);
    if (!note) {
      unresolvedRefs.push(fname);
      continue;
    }
    if (includedNotes.has(note.id)) continue;

    const noteAST = parse(note.body);
    expandRefsInAST(noteAST, notesById, 0, includedNotes, unresolvedRefs, note.fname, parse);
    rootAST.children.push(...noteAST.children);
    includedNotes.add(note.id);
  }

  // Append discovered compose notes
  for (const fname of profile.discovered) {
    const note = findNoteByFname(fname, notesById);
    if (!note) {
      unresolvedRefs.push(fname);
      continue;
    }
    if (includedNotes.has(note.id)) continue;

    const noteAST = parse(note.body);
    expandRefsInAST(noteAST, notesById, 0, includedNotes, unresolvedRefs, note.fname, parse);
    rootAST.children.push(...noteAST.children);
    includedNotes.add(note.id);
  }

  return {
    ast: rootAST,
    includedNotes: Array.from(includedNotes),
    unresolvedRefs,
  };
}

/**
 * Convert AST assembly result to the legacy AssembledDocument shape.
 * This allows gradual migration of downstream backends.
 */
export type ASTSerializer = (ast: Root) => string;

let defaultSerializer: ASTSerializer | undefined;

function getDefaultSerializer(): ASTSerializer {
  if (!defaultSerializer) {
    const { remark } = require("remark");
    defaultSerializer = (ast: Root) => remark().stringify(ast as any);
  }
  return defaultSerializer;
}

export function astToAssembledDocument(
  astResult: ReturnType<typeof assembleDocumentAST>,
  serializer?: ASTSerializer
): AssembledDocument {
  const { ast, includedNotes, unresolvedRefs } = astResult;
  const serialize = serializer || getDefaultSerializer();
  const body = serialize(ast);
  return {
    body,
    headingOffsets: {},
    includedNotes,
    unresolvedRefs,
  };
}

// ============================================================================
// AST transclusion
// ============================================================================

function expandRefsInAST(
  ast: Root,
  notesById: NotePropsByIdDict,
  depthOffset: number,
  visited: Set<string>,
  unresolved: string[],
  contextFname?: string,
  parser?: NoteParser
): void {
  // First apply heading depth adjustment to the whole tree
  if (depthOffset > 0) {
    shiftHeadings(ast, depthOffset);
  }

  // Walk the tree and replace refLinkV2 nodes
  visitParents(ast, (node: Node, ancestors: Parent[]) => {
    if (node.type !== REF_LINK_V2) return;

    const refNode = node as any;
    const fname = refNode.data?.link?.from?.fname || "";
    const anchor = refNode.data?.link?.data?.anchorStart;

    const targetNote = findNoteByFname(fname, notesById, contextFname);
    if (!targetNote) {
      unresolved.push(fname);
      replaceNodeInParent(ancestors, node, {
        type: "paragraph",
        children: [
          {
            type: "text",
            value: `Unresolved reference: [[${fname}]]`,
          } as any,
        ],
      } as any);
      return;
    }

    if (visited.has(targetNote.id)) {
      replaceNodeInParent(ancestors, node, {
        type: "paragraph",
        children: [
          {
            type: "text",
            value: `Note already included: [[${fname}]]`,
          } as any,
        ],
      } as any);
      return;
    }
    visited.add(targetNote.id);

    let noteBody = targetNote.body;
    if (anchor) {
      noteBody = extractSection(noteBody, anchor);
    }

    const noteDoc = extractDocFrontmatter(targetNote.custom);
    const shouldShift = noteDoc?.shiftHeadings !== false;
    const newDepthOffset = shouldShift ? depthOffset + 1 : depthOffset;

    const parse = parser || getDefaultParser();
    const noteAST = parse(noteBody);
    expandRefsInAST(
      noteAST,
      notesById,
      newDepthOffset,
      visited,
      unresolved,
      targetNote.fname,
      parse
    );

    // Replace the ref node with the note's AST children
    const parent = ancestors[ancestors.length - 1];
    if (parent) {
      const idx = parent.children.indexOf(node as any);
      if (idx >= 0) {
        parent.children.splice(idx, 1, ...noteAST.children);
      }
    }
  });
}

function shiftHeadings(node: Node, offset: number): void {
  if (node.type === "heading") {
    const h = node as Heading;
    h.depth = Math.min(h.depth + offset, 6) as any;
  }
  if ("children" in node && Array.isArray((node as Parent).children)) {
    (node as Parent).children.forEach((child) =>
      shiftHeadings(child as Node, offset)
    );
  }
}

function replaceNodeInParent(
  ancestors: Parent[],
  oldNode: Node,
  newNode: Node
): void {
  const parent = ancestors[ancestors.length - 1];
  if (!parent) return;
  const idx = parent.children.indexOf(oldNode as any);
  if (idx >= 0) {
    parent.children.splice(idx, 1, newNode as any);
  }
}

// Simple visitor that gives us ancestors
function visitParents(
  tree: Node,
  callback: (node: Node, ancestors: Parent[]) => void
): void {
  const walk = (node: Node, ancestors: Parent[]) => {
    callback(node, ancestors);
    if ("children" in node && Array.isArray((node as Parent).children)) {
      const parent = node as Parent;
      for (const child of parent.children) {
        walk(child as Node, [...ancestors, parent]);
      }
    }
  };
  walk(tree, []);
}


