import type { Plugin } from "unified";
export { PUNCTUATION_MARKS } from "./constants";
/** Hashtags have the form #foo, or #foo.bar, or #f123
 *
 * Hashtags are not allowed to start with numbers: this is to reserve them in
 * case we want to add Github issues integration, where issues look like #123
 *
 * Hashtags are also not allowed to contain any punctuation or quotation marks.
 * This allows them to be more easily mixed into text, for example:
 *
 * ```
 * This issue is #important, and should be prioritized.
 * ```
 *
 * Here, the tag is `#important` without the following comma.
 */
export declare const HASHTAG_REGEX: RegExp;
/** Same as `HASHTAG_REGEX`, except that that it doesn't have to be at the start of the string. */
export declare const HASHTAG_REGEX_LOOSE: RegExp;
/** Used for `getWordAtRange` queries. Too permissive, but the full regex breaks the function. */
export declare const HASHTAG_REGEX_BASIC: RegExp;
export declare class HashTagUtils {
    static extractTagFromMatch(match: RegExpMatchArray | null): string | undefined;
    /**
     *
     * @param text The text to check if it matches an hashtag.
     * @param matchLoose If true, a hashtag anywhere in the string will match. Otherwise the string must contain only the anchor.
     * @returns The identifier for the matched hashtag, or undefined if it did not match.
     */
    static matchHashtag: (text: string, matchLoose?: boolean) => string | undefined;
}
type PluginOpts = {};
declare const plugin: Plugin<[PluginOpts?]>;
export { plugin as hashtags };
export { PluginOpts as HashTagOpts };
