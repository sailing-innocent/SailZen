// Contains types that help with Dendron's unifiedjs markdown processor.

/** The expected output from the processor, if the processor is used to process or stringify a tree. */
export enum DendronASTDest {
  /**
   * @deprecated - no longer needed since we don't use the markdown preview
   * enhanced anymore
   */
  MD_ENHANCED_PREVIEW = "MD_ENHANCED_PREVIEW",
  MD_REGULAR = "MD_REGULAR",
  MD_DENDRON = "MD_DENDRON",
  HTML = "HTML",
  /**
   * SailZen Doc export mode: AST is processed for document generation
   * (LaTeX, Typst, Slidev, etc.)
   */
  DOC_EXPORT = "DOC_EXPORT",
  /**
   * SailZen Doc preview mode: lightweight preview of document formatting
   */
  DOC_PREVIEW = "DOC_PREVIEW",
}

/**
 * If processor should run in an alternative flavor
 */
export enum ProcFlavor {
  /**
   * No special processing
   */
  REGULAR = "REGULAR",
  /**
   * Apply publishing rules
   */
  PUBLISHING = "PUBLISHING",
  /**
   * Apply preview rules
   */
  PREVIEW = "PREVIEW",
  /**
   * Apply hover preview rules (used for the preview when hovering over a link)
   */
  HOVER_PREVIEW = "HOVER_PREVIEW",

  /**
   * Apply special hover preview rules for the backlinks panel.
   */
  BACKLINKS_PANEL_HOVER = "BACKLINK_HOVER",
}
