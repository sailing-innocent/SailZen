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
  /**
   * When this compose note is embedded via ![[...]], automatically shift
   * its headings down by one level (e.g. # → ##). Default: true.
   * Set to false if the note's headings are already at the desired level.
   */
  shiftHeadings?: boolean;
};

// ============================================================================
// Doc Profile - resolved document project descriptor
// ============================================================================

/** Resolved asset reference with its source path */
export type ResolvedAsset = {
  /** The reference key used in ::figure[cap](key) */
  ref: string;
  /** Absolute or vault-relative path to the image file */
  path: string;
  /** Optional width override */
  width?: string;
  /** Optional height override */
  height?: string;
  /** Optional caption override */
  caption?: string;
  /** Optional label override */
  label?: string;
};

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
  /** Asset references (raw keys from ::figure) */
  assets: string[];
  /** Resolved asset files with paths */
  resolvedAssets?: ResolvedAsset[];
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

// ============================================================================
// Document Section - for split-section LaTeX output
// ============================================================================

export type DocSection = {
  /** Section title */
  title: string;
  /** LaTeX content of the section */
  content: string;
  /** Heading level (1=chapter, 2=section, 3=subsection) */
  level: number;
  /** Suggested file name */
  fileName: string;
};

// ============================================================================
// Template System Types
// ============================================================================

export type DocTemplateVariable = {
  name: string;
  required?: boolean;
  type?: "string" | "array" | "boolean";
  default?: any;
};

export type DocTemplateConfig = {
  id: string;
  format: DocExportFormat;
  description: string;
  engine?: "pdflatex" | "xelatex" | "lualatex";
  requires?: string[];
  variables?: DocTemplateVariable[];
  sectioning?: {
    style: "numbered" | "unnumbered" | "chapter";
    maxDepth?: number;
  };
};

export type GeneratedDocument = {
  /** Main output file content */
  mainContent: string;
  /** Output file extension */
  ext: string;
  /** Additional text files to write (e.g., .bib, latexmkrc) */
  extraFiles: Array<{
    path: string;
    content: string;
  }>;
  /** Binary/asset files to copy (e.g., images) */
  assetFiles: Array<{
    srcPath: string;
    destPath: string;
  }>;
  /** Split sections for multi-file LaTeX projects */
  sections?: DocSection[];
  /** Compilation metadata */
  meta: {
    templateUsed: string;
    format: DocExportFormat;
    timestamp: number;
    engine?: string;
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
    doc.asset !== undefined ||
    doc.includes !== undefined ||
    doc.order !== undefined ||
    doc.anchors !== undefined ||
    doc.shiftHeadings !== undefined;
  if (!hasDocField) return undefined;
  return doc as DocFrontmatter;
}

// ============================================================================
// Helper: Check if a note has doc configuration
// ============================================================================

export function hasDocConfig(custom: any): boolean {
  return extractDocFrontmatter(custom) !== undefined;
}
