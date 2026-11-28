import type { Plugin } from "unified";
import { BlockAnchor } from "../types";
import { html } from "mdast-builder";
export declare const BLOCK_LINK_REGEX: RegExp;
export declare const BLOCK_LINK_REGEX_LOOSE: RegExp;
/**
 *
 * @param text The text to check if it matches an block anchor.
 * @param matchLoose If true, a block anchor anywhere in the string will match. Otherwise the string must contain only the anchor.
 * @returns The identifier for the match block anchor, or undefined if it did not match.
 */
export declare const matchBlockAnchor: (text: string, matchLoose?: boolean) => string | undefined;
type PluginOpts = {
    /** @deprecated */
    hideBlockAnchors?: boolean;
};
declare const plugin: Plugin<[PluginOpts?]>;
export declare function blockAnchor2htmlRaw(node: BlockAnchor, _opts?: PluginOpts): string;
export declare function blockAnchor2html(node: BlockAnchor, opts?: PluginOpts): ReturnType<typeof html>;
export { plugin as blockAnchors };
export { PluginOpts as BlockAnchorOpts };
