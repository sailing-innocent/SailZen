/**
 * SailZen Doc Engine Types
 *
 * Core type definitions for the Note-as-Source document compilation system.
 * These types extend the Sail note model with document-oriented metadata
 * for generating LaTeX, Typst, Slidev, and other output formats.
 */
// ============================================================================
// Helper: Extract doc frontmatter from a note's custom fields
// ============================================================================
export function extractDocFrontmatter(custom) {
    if (!custom)
        return undefined;
    // The doc field may be nested under custom.doc or directly under custom
    const doc = custom.doc || custom;
    if (!doc || typeof doc !== "object")
        return undefined;
    // Validate it's a doc frontmatter by checking for known fields
    const hasDocField = doc.role !== undefined ||
        doc.project !== undefined ||
        doc.exports !== undefined ||
        doc.meta !== undefined ||
        doc.bibtex !== undefined ||
        doc.asset !== undefined ||
        doc.includes !== undefined ||
        doc.order !== undefined ||
        doc.anchors !== undefined ||
        doc.shiftHeadings !== undefined;
    if (!hasDocField)
        return undefined;
    return doc;
}
// ============================================================================
// Helper: Check if a note has doc configuration
// ============================================================================
export function hasDocConfig(custom) {
    return extractDocFrontmatter(custom) !== undefined;
}
//# sourceMappingURL=docEngine.js.map