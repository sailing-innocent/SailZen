import type { Plugin } from "unified";
import { PageElementArgs, PageElementsPluginOpts } from "./types";
/** Tag name of page element markers. */
export declare const SAIL_ELEM_TAG = "sail-elem";
/** Attribute carrying the element key. */
export declare const SAIL_ELEM_KEY_ATTR = "key";
export type ParsedSailElem = {
    /** Element key, e.g. "PREFIX". Undefined when the key attr is missing. */
    key?: string;
    /** Named arguments from attributes other than `key`. */
    args: PageElementArgs;
    /** Inner fallback content of the paired form. */
    fallback?: string;
    /** The full original marker text, used for lossless round-trips. */
    raw: string;
};
/**
 * Parse a raw html node value into a page element marker. Returns undefined
 * when the value is not exactly one marker element.
 */
export declare function parseSailElem(rawValue: string): ParsedSailElem | undefined;
declare const plugin: Plugin<[PageElementsPluginOpts?], any>;
export { plugin as pageElements };
