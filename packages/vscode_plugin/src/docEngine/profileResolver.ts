import {
  DocExportConfig,
  DocMeta,
  DocProfile,
  extractDocFrontmatter,
  NoteProps,
  NotePropsByIdDict,
  ResolvedAsset,
} from "@saili/common-all";
import _ from "lodash";

// Simple inline logger to avoid dependency issues in test environment
const logger = {
  info: (payload: any) => {
    // eslint-disable-next-line no-console
    console.log(`[${payload.ctx || "profileResolver"}] ${payload.msg}`, payload);
  },
};

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

  const meta: DocMeta = {
    ...(docFm?.meta || {}),
    // Fall back to standard frontmatter fields if doc.meta doesn't specify them
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

  // Collect citations and assets from root note AND all included/discovered compose notes
  const allBodies = [rootNote.body];
  for (const fname of includes) {
    const note = findNoteByFname(fname, notesById);
    if (note) {
      allBodies.push(note.body);
    }
  }
  for (const fname of discovered) {
    const note = findNoteByFname(fname, notesById);
    if (note) {
      allBodies.push(note.body);
    }
  }
  const combinedBody = allBodies.join("\n\n");

  const citations = extractCitations(combinedBody);
  const assetRefs = extractAssetRefs(combinedBody);
  logger.info({
    ctx: "resolveProfile",
    msg: "extracted refs",
    citationCount: citations.length,
    assetRefCount: assetRefs.length,
    assetRefs,
  });

  const resolvedAssets = resolveAssets(assetRefs, notesById, projectName);
  logger.info({
    ctx: "resolveProfile",
    msg: "resolved assets",
    resolvedCount: resolvedAssets.length,
    resolvedAssets: resolvedAssets.map((a) => ({
      ref: a.ref,
      path: a.path,
      width: a.width,
    })),
  });

  return {
    rootNoteId: rootNote.id,
    rootNoteFname: rootNote.fname,
    vaultName: rootNote.vault?.name,
    exports,
    meta,
    includes,
    discovered,
    citations,
    assets: assetRefs,
    resolvedAssets,
  };
}

/**
 * Resolve asset reference keys to actual file paths.
 *
 * Resolution order:
 * 1. Look for an asset note with matching fname pattern: project.<name>.fig.<key>
 *    or direct fname match. Extract doc.asset.path from its frontmatter.
 * 2. Fall back to vault-relative path lookup.
 */
function resolveAssets(
  refs: string[],
  notesById: NotePropsByIdDict,
  projectName?: string
): ResolvedAsset[] {
  const resolved: ResolvedAsset[] = [];

  for (const ref of refs) {
    let found = false;

    // Strategy 1: Find asset note by project naming convention
    // e.g., ref "fig_pipeline" → normalized "fig.pipeline" → look for "project.testdoc.fig.pipeline"
    // The ref itself uses underscore separators that map to dot-separated fname hierarchy.
    if (projectName) {
      const normalizedRef = ref.toLowerCase().replace(/_/g, ".");
      const possibleFnames = [
        `${projectName}.${normalizedRef}`,   // project.testdoc.fig.pipeline
        `${projectName}.fig.${ref}`,          // project.testdoc.fig.fig_pipeline (fallback)
        `${projectName}.asset.${ref}`,        // project.testdoc.asset.fig_pipeline (fallback)
      ];

      logger.info({
        ctx: "resolveAssets",
        msg: `resolving ref "${ref}"`,
        possibleFnames,
        availableNoteFnames: Object.values(notesById).map((n) => n.fname),
      });

      for (const fname of possibleFnames) {
        const note = findNoteByFname(fname, notesById);
        if (note) {
          const docFm = extractDocFrontmatter(note.custom);
          logger.info({
            ctx: "resolveAssets",
            msg: `found note for fname "${fname}"`,
            noteId: note.id,
            role: docFm?.role,
            hasAssetPath: !!docFm?.asset?.path,
          });
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

    // Strategy 2: Direct fname match (e.g., note fname is exactly "fig_pipeline")
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

    // Strategy 3: Treat ref as a direct vault-relative path
    if (!found) {
      logger.info({
        ctx: "resolveAssets",
        msg: `falling back to direct path for ref "${ref}"`,
      });
      resolved.push({
        ref,
        path: ref,
      });
    }
  }

  return resolved;
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

/**
 * Extract ::table label references from markdown text
 */
export function extractTableRefs(body: string): string[] {
  const tableRegex = /::table\[[^\]]*\]\s*\(([^)]+)\)/g;
  const refs: string[] = [];
  let match;
  while ((match = tableRegex.exec(body)) !== null) {
    refs.push(match[1].trim());
  }
  return _.uniq(refs);
}

/**
 * Extract algorithm labels from markdown text
 */
export function extractAlgorithmRefs(body: string): string[] {
  const algRegex = /::algorithm\[[^\]]*\](?:\s*\{[^}]*\})?/g;
  // Algorithms don't have an external ref key in current syntax,
  // but we can count them for diagnostic purposes.
  const refs: string[] = [];
  let match;
  while ((match = algRegex.exec(body)) !== null) {
    refs.push(`algorithm_${refs.length}`);
  }
  return _.uniq(refs);
}

/**
 * Extract math environment names used in the document.
 */
export function extractMathEnvs(body: string): string[] {
  const envRegex = /::(theorem|lemma|corollary|proposition|definition|remark|proof)\b/g;
  const envs: string[] = [];
  let match;
  while ((match = envRegex.exec(body)) !== null) {
    envs.push(match[1]);
  }
  return _.uniq(envs);
}

/**
 * Extract conditional format blocks from markdown text.
 */
export function extractConditionals(body: string): Array<{ format: string; content: string }> {
  const condRegex = /::if-format\[([^\]]+)\]\s*\n([\s\S]*?)\n::end/g;
  const blocks: Array<{ format: string; content: string }> = [];
  let match;
  while ((match = condRegex.exec(body)) !== null) {
    blocks.push({ format: match[1].trim(), content: match[2] });
  }
  return blocks;
}
