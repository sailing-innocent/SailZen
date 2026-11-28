import type { Plugin } from "unified";
export declare const ZDOCTAG_REGEX: RegExp;
export declare const ZDOCTAG_REGEX_LOOSE: RegExp;
export declare class ZDocTagUtils {
    static extractTagFromMatch(match: RegExpMatchArray | null): string | undefined;
    static matchZDocTag: (text: string, matchLoose?: boolean) => string | undefined;
}
type PluginOpts = {};
declare const plugin: Plugin<[PluginOpts?]>;
export { plugin as zdocTags };
export { PluginOpts as ZDocTagOpts };
