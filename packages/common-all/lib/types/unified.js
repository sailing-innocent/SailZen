// Contains types that help with Sail's unifiedjs markdown processor.
/** The expected output from the processor, if the processor is used to process or stringify a tree. */
export var SailASTDest;
(function (SailASTDest) {
    /**
     * @deprecated - no longer needed since we don't use the markdown preview
     * enhanced anymore
     */
    SailASTDest["MD_ENHANCED_PREVIEW"] = "MD_ENHANCED_PREVIEW";
    SailASTDest["MD_REGULAR"] = "MD_REGULAR";
    SailASTDest["MD_SAIL"] = "MD_SAIL";
    SailASTDest["HTML"] = "HTML";
    /**
     * SailZen Doc export mode: AST is processed for document generation
     * (LaTeX, Typst, Slidev, etc.)
     */
    SailASTDest["DOC_EXPORT"] = "DOC_EXPORT";
    /**
     * SailZen Doc preview mode: lightweight preview of document formatting
     */
    SailASTDest["DOC_PREVIEW"] = "DOC_PREVIEW";
})(SailASTDest || (SailASTDest = {}));
/**
 * If processor should run in an alternative flavor
 */
export var ProcFlavor;
(function (ProcFlavor) {
    /**
     * No special processing
     */
    ProcFlavor["REGULAR"] = "REGULAR";
    /**
     * Apply publishing rules
     */
    ProcFlavor["PUBLISHING"] = "PUBLISHING";
    /**
     * Apply preview rules
     */
    ProcFlavor["PREVIEW"] = "PREVIEW";
    /**
     * Apply hover preview rules (used for the preview when hovering over a link)
     */
    ProcFlavor["HOVER_PREVIEW"] = "HOVER_PREVIEW";
    /**
     * Apply special hover preview rules for the backlinks panel.
     */
    ProcFlavor["BACKLINKS_PANEL_HOVER"] = "BACKLINK_HOVER";
})(ProcFlavor || (ProcFlavor = {}));
//# sourceMappingURL=unified.js.map