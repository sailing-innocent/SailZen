import { SailError } from "@saili/common-all";
import { SailASTDest } from "../types";
import { html } from "mdast-builder";
import { MDUtilsV5 } from "..";
// Letters, digits, dashes, and underscores.
// The underscores are an extension over Obsidian.
// Another extension is that it allows whitespace after the anchor.
export const BLOCK_LINK_REGEX = /^\^([\w-]+)\w*(\n|$)/;
export const BLOCK_LINK_REGEX_LOOSE = /\^([\w-]+)/;
/**
 *
 * @param text The text to check if it matches an block anchor.
 * @param matchLoose If true, a block anchor anywhere in the string will match. Otherwise the string must contain only the anchor.
 * @returns The identifier for the match block anchor, or undefined if it did not match.
 */
export const matchBlockAnchor = (text, matchLoose = true) => {
    const match = (matchLoose ? BLOCK_LINK_REGEX_LOOSE : BLOCK_LINK_REGEX).exec(text);
    if (match && match.length >= 2)
        return match[1];
    return undefined;
};
const plugin = function (opts) {
    attachParser(this);
    if (this.Compiler != null) {
        attachCompiler(this, opts);
    }
};
function attachParser(proc) {
    function locator(value, fromIndex) {
        return value.indexOf("^", fromIndex);
    }
    function inlineTokenizer(eat, value) {
        const match = BLOCK_LINK_REGEX.exec(value);
        if (match) {
            return eat(match[0])({
                type: "blockAnchor",
                // @ts-ignore
                value,
                id: match[1],
            });
        }
        return;
    }
    inlineTokenizer.locator = locator;
    const Parser = proc.Parser;
    if (!Parser)
        return;
    const inlineTokenizers = Parser.prototype.inlineTokenizers;
    const inlineMethods = Parser.prototype.inlineMethods;
    inlineTokenizers.blockAnchor = inlineTokenizer;
    inlineMethods.splice(inlineMethods.indexOf("link"), 0, "blockAnchor");
}
function attachCompiler(proc, _opts) {
    const Compiler = proc.Compiler;
    if (!Compiler)
        return;
    const visitors = Compiler.prototype.visitors;
    if (visitors) {
        visitors.blockAnchor = function (node) {
            const { dest } = MDUtilsV5.getProcData(proc);
            const fullId = node.id;
            switch (dest) {
                case SailASTDest.MD_SAIL:
                    return `^${fullId}`;
                case SailASTDest.MD_REGULAR:
                    // Regular markdown has no concept of anchors, so best to strip it out
                    return "";
                case SailASTDest.MD_ENHANCED_PREVIEW:
                    return `<a aria-hidden="true" class="block-anchor anchor-heading" id="${fullId}" href="#${fullId}">^${fullId}</a>`;
                default:
                    throw new SailError({ message: "Unable to render block anchor" });
            }
        };
    }
}
export function blockAnchor2htmlRaw(node, _opts) {
    const fullId = `^${node.id}`;
    return (`<a aria-hidden="true" class="block-anchor anchor-heading icon-link" id="${fullId}" href="#${fullId}">` +
        "</a>");
}
export function blockAnchor2html(node, opts) {
    return html(blockAnchor2htmlRaw(node, opts));
}
export { plugin as blockAnchors };
//# sourceMappingURL=blockAnchors.js.map