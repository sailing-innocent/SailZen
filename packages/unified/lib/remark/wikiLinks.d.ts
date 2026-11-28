import type { Plugin } from "unified";
export declare const LINK_REGEX: RegExp;
/**
 * Does not require wiki link be the start of the word
 */
export declare const LINK_REGEX_LOOSE: RegExp;
export declare const matchWikiLink: (text: string) => false | {
    link: import("./utils").ParseLinkV2Resp | null;
    start: number;
    end: number;
};
type PluginOpts = CompilerOpts;
type CompilerOpts = {
    convertObsidianLinks?: boolean;
    useId?: boolean;
    prefix?: string;
    convertLinks?: boolean;
};
/**
 * Remark plugin for wikilinks using new micromark architecture
 */
declare const plugin: Plugin<[CompilerOpts?]>;
export { plugin as wikiLinks };
export { PluginOpts as WikiLinksOpts };
