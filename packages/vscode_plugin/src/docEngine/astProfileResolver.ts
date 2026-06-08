/**
 * @file astProfileResolver.ts
 * @brief AST-based profile resolver for SailZen Doc Engine
 * @description Replaces regex-driven reference extraction with MDAST traversal.
 *   Collects citations, figures, tables, algorithms, and math environments
 *   by walking the assembled AST instead of scanning raw strings.
 */

import {
  DocExportConfig,
  DocMeta,
  DocProfile,
  extractDocFrontmatter,
  NoteProps,
  NotePropsByIdDict,
  ResolvedAsset,
} from "@saili/common-all";
import type { Node, Parent, Root } from "mdast";
import _ from "lodash";

const SAILZEN_CITE = "sailzenCite";
const SAILZEN_FIGURE = "sailzenFigure";
const SAILZEN_TABLE = "sailzenTable";
const SAILZEN_ALGORITHM = "sailzenAlgorithm";
const SAILZEN_MATH_ENV = "sailzenMathEnv";

// ============================================================================
// Public API
// ============================================================================

export function resolveProfileAST(
  rootNote: NoteProps,
  notesById: NotePropsByIdDict,
  assembledAST?: Root
): DocProfile {
  const docFm = extractDocFrontmatter(rootNote.custom);

  const exports: DocExportConfig[] = docFm?.exports || [
    { format: "latex", template: "article" },
  ];

  const meta: DocMeta = {
    ...(docFm?.meta || {}),
    title: docFm?.meta?.title || rootNote.title,
    abstract: docFm?.meta?.abstract || rootNote.desc || undefined,
    authors: docFm?.meta?.authors || rootNote.custom?.authors,
    keywords:
      docFm?.meta?.keywords ||
      (Array.isArray(rootNote.tags)
        ? rootNote.tags
        : rootNote.tags
          ? [rootNote.tags]
          : undefined),
  };

  const projectName = docFm?.project;
  const includes: string[] = docFm?.includes || [];

  // Auto-discover compose notes
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
    discovered.sort((a, b) => {
      const noteA = findNoteByFname(a, notesById);
      const noteB = findNoteByFname(b, notesById);
      const orderA = extractDocFrontmatter(noteA?.custom)?.order ?? Infinity;
      const orderB = extractDocFrontmatter(noteB?.custom)?.order ?? Infinity;
      return orderA - orderB || a.localeCompare(b);
    });
  }

  // Extract references from assembled AST
  const refs = extractReferencesFromAST(assembledAST);

  const resolvedAssets = resolveAssets(refs.assets, notesById, projectName);

  return {
    rootNoteId: rootNote.id,
    rootNoteFname: rootNote.fname,
    vaultName: rootNote.vault?.name,
    exports,
    meta,
    includes,
    discovered,
    citations: refs.citations,
    assets: refs.assets,
    resolvedAssets,
  };
}

// ============================================================================
// AST reference extraction
// ============================================================================

export type ExtractedReferences = {
  citations: string[];
  assets: string[];
  tables: string[];
  algorithms: string[];
  mathEnvs: string[];
};

export function extractReferencesFromAST(
  ast?: Root
): ExtractedReferences {
  const citations: string[] = [];
  const assets: string[] = [];
  const tables: string[] = [];
  const algorithms: string[] = [];
  const mathEnvs: string[] = [];

  if (!ast) {
    return { citations, assets, tables, algorithms, mathEnvs };
  }

  visitAST(ast, (node: Node) => {
    switch (node.type) {
      case SAILZEN_CITE: {
        const cite = node as any;
        if (cite.keys && Array.isArray(cite.keys)) {
          citations.push(...cite.keys);
        }
        break;
      }
      case SAILZEN_FIGURE: {
        const fig = node as any;
        if (fig.src) assets.push(fig.src);
        break;
      }
      case SAILZEN_TABLE: {
        const tab = node as any;
        if (tab.label) tables.push(tab.label);
        break;
      }
      case SAILZEN_ALGORITHM: {
        const alg = node as any;
        algorithms.push(alg.label || alg.title || "algorithm");
        break;
      }
      case SAILZEN_MATH_ENV: {
        const env = node as any;
        mathEnvs.push(env.envType || "mathEnv");
        break;
      }
    }
  });

  return {
    citations: _.uniq(citations),
    assets: _.uniq(assets),
    tables: _.uniq(tables),
    algorithms: _.uniq(algorithms),
    mathEnvs: _.uniq(mathEnvs),
  };
}

function visitAST(node: Node, callback: (node: Node) => void): void {
  callback(node);
  if ("children" in node && Array.isArray((node as Parent).children)) {
    for (const child of (node as Parent).children) {
      visitAST(child as Node, callback);
    }
  }
}

// ============================================================================
// Asset resolution (copied from profileResolver for standalone use)
// ============================================================================

function resolveAssets(
  refs: string[],
  notesById: NotePropsByIdDict,
  projectName?: string
): ResolvedAsset[] {
  const resolved: ResolvedAsset[] = [];

  for (const ref of refs) {
    let found = false;

    if (projectName) {
      const normalizedRef = ref.toLowerCase().replace(/_/g, ".");
      const possibleFnames = [
        `${projectName}.${normalizedRef}`,
        `${projectName}.fig.${ref}`,
        `${projectName}.asset.${ref}`,
      ];

      for (const fname of possibleFnames) {
        const note = findNoteByFname(fname, notesById);
        if (note) {
          const docFm = extractDocFrontmatter(note.custom);
          if (docFm?.role === "asset" && docFm?.asset?.path) {
            resolved.push({
              ref,
              path: docFm.asset.path,
              width: docFm.asset.width,
              height: docFm.asset.height,
              caption: docFm.asset.caption,
              label: docFm.asset.label,
            });
            found = true;
            break;
          }
        }
      }
    }

    if (!found) {
      const note = findNoteByFname(ref, notesById);
      if (note) {
        const docFm = extractDocFrontmatter(note.custom);
        if (docFm?.role === "asset" && docFm?.asset?.path) {
          resolved.push({
            ref,
            path: docFm.asset.path,
            width: docFm.asset.width,
            height: docFm.asset.height,
            caption: docFm.asset.caption,
            label: docFm.asset.label,
          });
          found = true;
        }
      }
    }

    if (!found) {
      resolved.push({ ref, path: ref });
    }
  }

  return resolved;
}

function findNoteByFname(
  fname: string,
  notesById: NotePropsByIdDict
): NoteProps | undefined {
  for (const note of Object.values(notesById)) {
    if (note.fname === fname) return note;
  }
  return undefined;
}
