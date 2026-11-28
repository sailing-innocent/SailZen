import { SailASTDest, } from "@saili/common-all";
export { VFile } from "vfile";
export { SailASTDest };
export var SailASTTypes;
(function (SailASTTypes) {
    SailASTTypes["WIKI_LINK"] = "wikiLink";
    SailASTTypes["REF_LINK_V2"] = "refLinkV2";
    SailASTTypes["BLOCK_ANCHOR"] = "blockAnchor";
    SailASTTypes["HASHTAG"] = "hashtag";
    SailASTTypes["ZDOCTAG"] = "zdoctag";
    SailASTTypes["EXTENDED_IMAGE"] = "extendedImage";
    // SailZen Doc extensions
    SailASTTypes["SAILZEN_CITE"] = "sailzenCite";
    SailASTTypes["SAILZEN_FIGURE"] = "sailzenFigure";
    SailASTTypes["SAILZEN_TABLE"] = "sailzenTable";
    SailASTTypes["SAILZEN_MATH_ENV"] = "sailzenMathEnv";
    SailASTTypes["SAILZEN_ALGORITHM"] = "sailzenAlgorithm";
    SailASTTypes["SAILZEN_IF_FORMAT"] = "sailzenIfFormat";
    /** Page element marker, e.g. `$$PREFIX$$`. See remark/pageElements. */
    SailASTTypes["PAGE_ELEMENT"] = "pageElement";
    // Not sail-specific, included here for convenience
    SailASTTypes["ROOT"] = "root";
    SailASTTypes["HEADING"] = "heading";
    SailASTTypes["LIST"] = "list";
    SailASTTypes["LIST_ITEM"] = "listItem";
    SailASTTypes["PARAGRAPH"] = "paragraph";
    SailASTTypes["TEXT"] = "text";
    SailASTTypes["TABLE"] = "table";
    SailASTTypes["TABLE_ROW"] = "tableRow";
    SailASTTypes["TABLE_CELL"] = "tableCell";
    SailASTTypes["IMAGE"] = "image";
    SailASTTypes["FRONTMATTER"] = "yaml";
    SailASTTypes["LINK"] = "link";
    SailASTTypes["CODE"] = "code";
    SailASTTypes["INLINE_CODE"] = "inlineCode";
    SailASTTypes["FOOTNOTE_DEFINITION"] = "footnoteDefinition";
    SailASTTypes["FOOTNOTE_REFERENCE"] = "footnoteReference";
    SailASTTypes["HTML"] = "html";
    SailASTTypes["YAML"] = "yaml";
})(SailASTTypes || (SailASTTypes = {}));
export var VaultMissingBehavior;
(function (VaultMissingBehavior) {
    VaultMissingBehavior[VaultMissingBehavior["FALLBACK_TO_ORIGINAL_VAULT"] = 0] = "FALLBACK_TO_ORIGINAL_VAULT";
    VaultMissingBehavior[VaultMissingBehavior["THROW_ERROR"] = 1] = "THROW_ERROR";
})(VaultMissingBehavior || (VaultMissingBehavior = {}));
//# sourceMappingURL=types.js.map