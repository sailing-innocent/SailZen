/**
 * SailZen Doc Engine Types
 * 
 * Core type definitions for the Note-as-Source document compilation system.
 * These types extend the Dendron note model with document-oriented metadata
 * for generating LaTeX, Typst, Slidev, and other output formats.
 */

// ============================================================================
// Doc Role - the role of a note within the document system
// ============================================================================

export type DocRole = "source" | "compose" | "standalone" | "asset" | "bib";

// ============================================================================
// Doc Export Configuration - per-format output settings
// ============================================================================

export type DocExportFormat = "latex" | "typst" | "slidev" | "markdown";

export type DocExportConfig = {
  format: DocExportFormat;
  template?: string;
  outDir?: string;
  vars?: Record<string, any>;
  preProcess?: string;
  postProcess?: string;
};

// ============================================================================
// Doc Metadata - bibliographic and publishing metadata
// ============================================================================

export type DocAuthor = {
  name: string;
  affiliation?: string;
  email?: string;
  orcid?: string;
};

export type DocMeta = {
  authors?: DocAuthor[];
  conference?: string;
  journal?: string;
  keywords?: string[];
  abstract?: string;
  doi?: string;
  year?: number;
  [key: string]: any;
};

// ============================================================================
// BibTeX Entry - bibliographic record embedded in a note
// ============================================================================

export type BibTeXEntry = {
  type: string;
  key: string;
  fields: Record<string, string>;
};

// ============================================================================
// Asset Reference - image/table/algorithm resource
// ============================================================================

export type DocAsset = {
  path?: string;
  width?: string;
  height?: string;
  caption?: string;
  label?: string;
};

// ============================================================================
// Doc Frontmatter - the `doc` field in note frontmatter
// ============================================================================

export type DocFrontmatter = {
  role?: DocRole;
  project?: string;
  order?: number;
  anchors?: string[];
  /** Explicitly include these note fnames in the document */
  includes?: string[];
  exports?: DocExportConfig[];
  meta?: DocMeta;
  bibtex?: BibTeXEntry;
  asset?: DocAsset;
};

// ============================================================================
// Doc Profile - resolved document project descriptor
// ============================================================================

export type DocProfile = {
  /** The ID of the root (standalone) note */
  rootNoteId: string;
  /** The fname of the root note */
  rootNoteFname: string;
  /** The vault name of the root note */
  vaultName?: string;
  /** Resolved export configurations */
  exports: DocExportConfig[];
  /** Resolved document metadata */
  meta: DocMeta;
  /** Explicitly included note fnames */
  includes: string[];
  /** Auto-discovered compose note fnames */
  discovered: string[];
  /** Citation keys referenced in the document */
  citations: string[];
  /** Asset references */
  assets: string[];
};

// ============================================================================
// Document Assembly Result
// ============================================================================

export type AssembledDocument = {
  /** The assembled markdown content */
  body: string;
  /** Map of note fname → original heading depth offset */
  headingOffsets: Record<string, number>;
  /** List of all notes included in the assembly */
  includedNotes: string[];
  /** List of unresolved references */
  unresolvedRefs: string[];
};

// ============================================================================
// Backend Generation Result
// ============================================================================

export type GeneratedDocument = {
  /** Main output file content */
  mainContent: string;
  /** Output file extension */
  ext: string;
  /** Additional files to write (e.g., .bib, sections/) */
  extraFiles: Array<{
    path: string;
    content: string;
  }>;
  /** Compilation metadata */
  meta: {
    templateUsed: string;
    format: DocExportFormat;
    timestamp: number;
  };
};

// ============================================================================
// Helper: Extract doc frontmatter from a note's custom fields
// ============================================================================

export function extractDocFrontmatter(custom: any): DocFrontmatter | undefined {
  if (!custom) return undefined;
  // The doc field may be nested under custom.doc or directly under custom
  const doc = custom.doc || custom;
  if (!doc || typeof doc !== "object") return undefined;
  // Validate it's a doc frontmatter by checking for known fields
  const hasDocField =
    doc.role !== undefined ||
    doc.project !== undefined ||
    doc.exports !== undefined ||
    doc.meta !== undefined ||
    doc.bibtex !== undefined ||
    doc.asset !== undefined;
  if (!hasDocField) return undefined;
  return doc as DocFrontmatter;
}

// ============================================================================
// Helper: Check if a note has doc configuration
// ============================================================================

export function hasDocConfig(custom: any): boolean {
  return extractDocFrontmatter(custom) !== undefined;
}
