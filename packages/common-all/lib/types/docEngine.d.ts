/**
 * SailZen Doc Engine Types
 *
 * Core type definitions for the Note-as-Source document compilation system.
 * These types extend the Sail note model with document-oriented metadata
 * for generating LaTeX, Typst, Slidev, and other output formats.
 */
export type DocRole = "source" | "compose" | "standalone" | "asset" | "bib";
export type DocExportFormat = "latex" | "typst" | "slidev" | "markdown";
export type DocExportConfig = {
    format: DocExportFormat;
    template?: string;
    outDir?: string;
    vars?: Record<string, any>;
    preProcess?: string;
    postProcess?: string;
};
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
export type BibTeXEntry = {
    type: string;
    key: string;
    fields: Record<string, string>;
};
export type DocAsset = {
    path?: string;
    width?: string;
    height?: string;
    caption?: string;
    label?: string;
};
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
    engine?: "pdflatex" | "xelatex" | "lualatex" | "typst";
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
    /** Template dependency files to copy into the format-specific output directory (e.g., .cls, .sty) */
    templateFiles?: Array<{
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
export declare function extractDocFrontmatter(custom: any): DocFrontmatter | undefined;
export declare function hasDocConfig(custom: any): boolean;
