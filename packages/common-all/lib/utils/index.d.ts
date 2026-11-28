import GithubSlugger from "github-slugger";
import { minimatch } from "minimatch";
import semver from "semver";
import type { Result } from "neverthrow";
import { NotePropsMeta } from "..";
import { ISailError } from "../error";
import { DHookDict, NoteChangeEntry, NoteProps } from "../types";
import { GithubConfig } from "../types/configs/publishing/github";
import { SailPublishingConfig, DuplicateNoteBehavior, HierarchyConfig, SearchMode } from "../types/configs/publishing/publishing";
import { TaskConfig } from "../types/configs/workspace/task";
import { DVault } from "../types/DVault";
import { SailConfig, SailCommandConfig, SailPreviewConfig, SailWorkspaceConfig, GiscusConfig, JournalConfig, LookupConfig, NonNoteFileLinkAnchorType, NoteLookupConfig, ScratchConfig } from "../types/configs";
export { ok, Ok, err, Err, Result, okAsync, errAsync, ResultAsync, fromThrowable, fromPromise, fromSafePromise, } from "neverthrow";
export * from "./lookup";
export * from "./publishUtils";
export * from "./vscode-utils";
/**
 * Sail utilities
 */
export declare class DUtils {
    static minimatch: {
        (p: string, pattern: string, options?: import("minimatch").MinimatchOptions): boolean;
        sep: import("minimatch").Sep;
        GLOBSTAR: typeof import("minimatch").GLOBSTAR;
        filter: (pattern: string, options?: import("minimatch").MinimatchOptions) => (p: string) => boolean;
        defaults: (def: import("minimatch").MinimatchOptions) => typeof minimatch;
        braceExpand: (pattern: string, options?: import("minimatch").MinimatchOptions) => string[];
        makeRe: (pattern: string, options?: import("minimatch").MinimatchOptions) => false | import("minimatch").MMRegExp;
        match: (list: string[], pattern: string, options?: import("minimatch").MinimatchOptions) => string[];
        AST: typeof import("minimatch").AST;
        Minimatch: typeof import("minimatch").Minimatch;
        escape: (s: string, { windowsPathsNoEscape, magicalBraces, }?: Pick<import("minimatch").MinimatchOptions, "windowsPathsNoEscape" | "magicalBraces">) => string;
        unescape: (s: string, { windowsPathsNoEscape, magicalBraces, }?: Pick<import("minimatch").MinimatchOptions, "windowsPathsNoEscape" | "magicalBraces">) => string;
    };
    static semver: typeof semver;
}
export declare const getSlugger: () => GithubSlugger;
/**
 * determine if given parameter is numeric
 * https://stackoverflow.com/questions/18082/validate-decimal-numbers-in-javascript-isnumeric/1830844#1830844
 * @param n
 * @returns boolean
 */
export declare const isNumeric: (n: any) => boolean;
export declare function isBlockAnchor(anchor?: string): boolean;
export declare function isLineAnchor(anchor?: string): boolean;
/** A type guard for things that are not undefined.
 *
 * This is equivalent to !_.isUndefined(), except that it provides a type guard
 * ensuring the parameter is not undefined. This is useful when filtering:
 *
 * function foo(list: (string | undefined)[]) {
 *   const stringsOnly = list.filter(isNotUndefined);
 * }
 *
 * This will give stringsOnly the type string[]. Without the type guard, it would have
 * received the type (string | undefined)[] despite the fact that we filtered out undefined.
 */
export declare function isNotUndefined<T>(t: T | undefined): t is T;
export declare function isNotNull<T>(t: T | null): t is T;
/**
 * Check if the value u is a falsy value.
 */
export declare function isFalsy(u: any): boolean;
/** Given a string, return a random color as a HTML color code.
 *
 * The same string will always generate the same color, and different strings will get different random colors.
 */
export declare function randomColor(text: string): string;
/** Only some colors are recognized, other colors will be returned without being modified.
 *
 * Examples of recognized colors:
 * * #45AB35
 * * rgb(123, 23, 45)
 * * rgb(123 23 45)
 * * hsl(123, 23%, 45%)
 * * hsl(123 23% 45%)
 *
 * This function does not verify that the input colors are valid, but as long as a valid color is passed in
 * it will not generate an invalid color.
 *
 * @param color
 * @param translucency A number between 0 and 1, with 0 being fully transparent and 1 being fully opaque.
 * @returns
 */
export declare function makeColorTranslucent(color: string, translucency: number): string;
/** Memoizes function results, but allows a custom function to decide if the
 * value needs to be recalculated.
 *
 * This function pretty closely reproduces the memoize function of Lodash,
 * except that it allows a custom function to override whether a cached value
 * should be updated.
 *
 * Similar to the lodash memoize, the backing cache is exposed with the
 * `memoizedFunction.cache`. You can use this
 *
 * @param fn The function that is being memoized. This function will run when
 * the cache needs to be updated.
 * @param keyFn A function that given the inputs to `fn`, returns a key. Two
 * inputs that will have the same output should resolve to the same key. The key
 * may be anything, but it's recommended to use something simple like a string
 * or integer. By default, the first argument to `fn` is stringified and used as
 * the key (similar to lodash memoize)
 * @param shouldUpdate If this function returns true, the wrapped function will
 * run again and the cached value will update. `shouldUpdate` is passed the
 * cached result, and the new inputs. By default, it will only update if there
 * is a cache miss.
 * @param maxCache The maximum number of items to cache.
 */
export declare function memoize<Inputs extends any[], Key extends {}, Output extends {}>({ fn, keyFn, shouldUpdate, maxCache, }: {
    fn: (...args: Inputs) => Output;
    keyFn?: (...args: Inputs) => Key;
    shouldUpdate?: (previous: Output, ...args: Inputs) => boolean;
    maxCache?: number;
}): (...args: Inputs) => Output;
export declare class FIFOQueue<T> {
    private _internalQueue;
    constructor(init?: T[]);
    enqueue(item: T): void;
    enqueueAll(items: T[]): void;
    dequeue(): T | undefined;
    get length(): number;
}
/** Similar to lodash `_.groupBy`, except not limited to string keys. */
export declare function groupBy<K, V>(collection: V[], iteratee: (value: V, index: number) => K): Map<K, V[]>;
export declare function mapValues<K, I, O>(inMap: Map<K, I>, applyFn: (valueIn: I) => O): Map<K, O>;
/** Throttles a given async function so that it is only executed again once the first execution is complete.
 *
 * Similar to lodash _.throttle, except that:
 * 1. It's aware of the inputs, and will only throttle calls where `keyFn` returns the same key for the inputs of that call.
 * 2. Rather than a set timeout, it will keep throttling until the first async call is complete or if set, the `maxTimeout` is reached.
 *
 * @param fn The function to throttle.
 * @param keyFn A function that takes the inputs to an `fn` call and turns them into an identifying key, where to calls with same input will have the same key.
 * @param timeout Optional, in ms. If set, the throttle will not throttle for more than this much time. Once the timeout is reached, the next call will be allowed to execute.
 * @returns The throttled function. This function will return its results if it got executed, or undefined it it was throttled.
 */
export declare function throttleAsyncUntilComplete<I extends any[], O>({ fn, keyFn, timeout, }: {
    fn: (...args: I) => Promise<O>;
    keyFn: (...args: I) => string | number;
    timeout?: number;
}): (...args: I) => Promise<O | undefined>;
type DebounceStates = "timeout" | "execute" | "trailing";
type DebounceStateMap = Map<string | number, DebounceStates>;
/** Debounces a given async function so that it is only executed again once the first execution is complete.
 *
 * Similar to lodash _.debounce, except that:
 * 1. It's aware of the inputs, and will only debounce calls where `keyFn` returns the same key for the inputs of that call.
 * 2. In addition to the timeout, it will also debouce calls while the async function is executing.
 *
 * Differently from `throttleAsyncUntilComplete`, this will wait for the timeout to expire before running the function for the first time.
 * Additionally, if any calls occur while the function is being executed and `trailing` is set,
 * another timeout and execution will happen once the current execution is done.
 * For example, consider this timeline where the arrows are calls to the debounced function.
 *
 * ```
 * +---------+---------+---------+---------+
 * | timeout | execute | timeout | execute |
 * +---------+---------+---------+---------+
 * ^   ^   ^     ^
 * ```
 * The timeout starts at first function call, all calls during that time are debounced, and the function finally executes after the timeout.
 * Because another function call happens during the execution of the async function, another timeout and execution trigger right after the
 * first is done (this will only happen if trailing is set). After that point, no more function calls occur so no more timeouts or executions happen.
 *
 * **Check `windowDecorations.ts` for an example of how this is used. It was primarily purpose-built for that.
 *
 * @param fn The function to debounce.
 * @param keyFn A function that takes the inputs to an `fn` call and turns them into an identifying key, where to calls with same input will have the same key.
 * @param timeout In ms. The function will not execute until this much time has passed. In other words, there will be at least this much time between executions.
 * @param trailing Optional. If set, an additional execution will be done to respond to calls during the execute phase.
 * @returns An object containing the debounced function, and the
 */
export declare function debounceAsyncUntilComplete<I extends any[], O>({ fn, keyFn, timeout, trailing, }: {
    fn: (...args: I) => Promise<O>;
    keyFn: (...args: I) => string | number;
    timeout: number;
    trailing?: boolean;
}): {
    debouncedFn: (...args: I) => void;
    states: DebounceStateMap;
};
export declare function genHash(contents: any): string;
export declare class TagUtils {
    /** Removes `oldTag` from the frontmatter tags of `note` and replaces it with `newTag`, if any. */
    static replaceTag({ note, oldTag, newTag, }: {
        note: NoteProps;
        oldTag: string;
        newTag?: string;
    }): void;
}
/** Makes a single property within a type optional.
 *
 * Example:
 * ```ts
 * function foo(note: Optional<NoteProps, "title">) {
 *   let title = note.title;
 *   if (title === undefined) title = "default title";
 *   // ...
 * }
 * ```
 */
export type Optional<T, K extends keyof T> = Pick<Partial<T>, K> & Omit<T, K>;
/**
 * simple Option type
 * See https://en.wikipedia.org/wiki/Option_type
 */
export type Option<T> = T | undefined;
/** Makes a single property within a type required. */
export type NonOptional<T, K extends keyof T> = Pick<Required<T>, K> & Omit<T, K>;
/** Makes not just the top level, but all nested properties optional. */
export type DeepPartial<T> = {
    [P in keyof T]?: DeepPartial<T[P]>;
};
export type ConfigVaildationResp = {
    isValid: boolean;
    reason?: "client" | "config";
    isSoftMapping?: boolean;
    minCompatClientVersion?: string;
    minCompatConfigVersion?: string;
};
export declare class ConfigUtils {
    static genDefaultConfig(): SailConfig;
    /**
     * This is different from {@link genDefaultConfig}
     * as it includes updated settings that we don't want to set as
     * defaults for backward compatibility reasons
     */
    static genLatestConfig(defaults?: DeepPartial<SailConfig>): SailConfig;
    static getProp<K extends keyof SailConfig>(config: SailConfig, key: K): SailConfig[K];
    static getCommands(config: SailConfig): SailCommandConfig;
    static getWorkspace(config: SailConfig): SailWorkspaceConfig;
    static getPreview(config: SailConfig): SailPreviewConfig;
    static getPublishing(config: SailConfig): SailPublishingConfig;
    static getVaults(config: SailConfig): DVault[];
    static getHooks(config: SailConfig): DHookDict | undefined;
    static getJournal(config: SailConfig): JournalConfig;
    static getScratch(config: SailConfig): ScratchConfig;
    static getTask(config: SailConfig): TaskConfig;
    static getLookup(config: SailConfig): LookupConfig;
    static getEnableFMTitle(config: SailConfig, shouldApplyPublishRules?: boolean): boolean | undefined;
    static getEnableNoteTitleForLink(config: SailConfig, shouldApplyPublishRules?: boolean): boolean | undefined;
    static getEnableKatex(config: SailConfig, shouldApplyPublishRules?: boolean): boolean | undefined;
    static getHierarchyConfig(config: SailConfig): {
        [key: string]: HierarchyConfig;
    } | undefined;
    static getGithubConfig(config: SailConfig): GithubConfig | undefined;
    static getGiscusConfig(config: SailConfig): GiscusConfig | undefined;
    static getLogo(config: SailConfig): string | undefined;
    static getAssetsPrefix(config: SailConfig): string | undefined;
    static getEnableRandomlyColoredTags(config: SailConfig): boolean | undefined;
    static getEnableFrontmatterTags(opts: {
        config: SailConfig;
        shouldApplyPublishRules: boolean;
    }): boolean | undefined;
    static getEnableHashesForFMTags(opts: {
        config: SailConfig;
        shouldApplyPublishRules: boolean;
    }): boolean | undefined;
    static getEnablePrettlyLinks(config: SailConfig): boolean | undefined;
    static getGATracking(config: SailConfig): string | undefined;
    static getSiteLastModified(config: SailConfig): boolean | undefined;
    static getSiteLogoUrl(config: SailConfig): string | undefined;
    static getEnablePrettyRefs(config: SailConfig, opts?: {
        note?: NotePropsMeta;
        shouldApplyPublishRules?: boolean;
    }): boolean | undefined;
    /**
     * NOTE: _config currently doesn't have a `global` object. We're keeping it here
     * to make using the API easier when we do add it
     */
    static getEnableChildLinks(_config: SailConfig, opts?: {
        note?: NotePropsMeta;
    }): boolean;
    static getEnableBackLinks(_config: SailConfig, opts?: {
        note?: NotePropsMeta;
        shouldApplyPublishingRules?: boolean;
    }): boolean;
    static getHierarchyDisplayConfigForPublishing(config: SailConfig): {
        hierarchyDisplay: boolean | undefined;
        hierarchyDisplayTitle: string | undefined;
    };
    static getNonNoteLinkAnchorType(config: SailConfig): NonNoteFileLinkAnchorType;
    static getAliasMode(config: SailConfig): "title" | "none";
    static getVersion(config: SailConfig): number;
    static getSearchMode(config: SailConfig): SearchMode;
    static setProp<K extends keyof SailConfig>(config: SailConfig, key: K, value: SailConfig[K]): void;
    static setCommandsProp<K extends keyof SailCommandConfig>(config: SailConfig, key: K, value: SailCommandConfig[K]): void;
    static setWorkspaceProp<K extends keyof SailWorkspaceConfig>(config: SailConfig, key: K, value: SailWorkspaceConfig[K]): void;
    static setPublishProp<K extends keyof SailPublishingConfig>(config: SailConfig, key: K, value: SailPublishingConfig[K]): void;
    /**
     * Set properties under the publishing.github namaspace (v5+ config)
     */
    static setGithubProp<K extends keyof GithubConfig>(config: SailConfig, key: K, value: GithubConfig[K]): void;
    static isSailPublishingConfig(config: unknown): config is SailPublishingConfig;
    static overridePublishingConfig(config: SailConfig, value: SailPublishingConfig): {
        publishing: SailPublishingConfig;
        version: number;
        global?: import("..").SailGlobalConfig;
        commands: SailCommandConfig;
        workspace: SailWorkspaceConfig;
        preview: SailPreviewConfig;
        dev?: import("..").SailDevConfig;
    };
    static unsetProp<K extends keyof SailConfig>(config: SailConfig, key: K): void;
    static unsetPublishProp<K extends keyof SailPublishingConfig>(config: SailConfig, key: K): void;
    static setDuplicateNoteBehavior(config: SailConfig, value: DuplicateNoteBehavior): void;
    static unsetDuplicateNoteBehavior(config: SailConfig): void;
    static setVaults(config: SailConfig, value: DVault[]): void;
    /** Finds the matching vault in the config, and uses the callback to update it. */
    static updateVault(config: SailConfig, vaultToUpdate: DVault, updateCb: (vault: DVault) => DVault): void;
    static setNoteLookupProps<K extends keyof NoteLookupConfig>(config: SailConfig, key: K, value: NoteLookupConfig[K]): void;
    static setJournalProps<K extends keyof JournalConfig>(config: SailConfig, key: K, value: JournalConfig[K]): void;
    static setScratchProps<K extends keyof ScratchConfig>(config: SailConfig, key: K, value: ScratchConfig[K]): void;
    static setHooks(config: SailConfig, value: DHookDict): void;
    static setPreviewProps<K extends keyof SailPreviewConfig>(config: SailConfig, key: K, value: SailPreviewConfig[K]): void;
    static setNonNoteLinkAnchorType(config: SailConfig, value: NonNoteFileLinkAnchorType): void;
    static setAliasMode(config: SailConfig, aliasMode: "title" | "none"): void;
    static configIsValid(opts: {
        clientVersion: string;
        configVersion: number | undefined;
    }): ConfigVaildationResp;
    static detectMissingDefaults(opts: {
        config: Partial<SailConfig>;
        defaultConfig?: SailConfig;
    }): {
        needsBackfill: boolean;
        backfilledConfig: SailConfig;
    };
    static detectDeprecatedConfigs(opts: {
        config: Partial<SailConfig>;
        deprecatedPaths: string[];
    }): string[];
    static getConfigDescription: (conf: string) => any;
    /**
     * Given an config object and an optional array of lodash property path,
     * omit the properties from the object and flatten it
     * The result will be a flat array of path-value pairs
     *
     * Each pair will contain a path and a value.
     * The value is either a primitive value, or a stringified array.
     *
     * If comparing the array value of a config is unnecessary,
     * make sure to add it to the omit path.
     */
    static flattenConfigObject(opts: {
        obj: Object;
        omitPaths?: string[];
    }): {
        path: string;
        value: any;
    }[];
    /**
     * Given a config, find the difference compared to the default.
     *
     * This is used to track changes from the default during activation.
     */
    static findDifference(opts: {
        config: SailConfig;
    }): {
        path: string;
        value: any;
    }[];
    /**
     * Parses an unkown input into a SailConfig
     * @param input
     */
    static parse(input: unknown): Result<SailConfig, ISailError>;
}
/**
 * Make name safe for sail
 * @param name
 * @param opts
 */
export declare function cleanName(name: string): string;
/**
 * Given a path on any platform, convert it to a unix style path. Avoid using this with absolute paths.
 */
export declare function normalizeUnixPath(fsPath: string): string;
/** Wrapper(s) for easier testing, to wrap functions where we don't want to mock the global function. */
export declare class Wrap {
    /** A useless wrapper around `setTimeout`. Useful for testing.
     *
     * If you are testing code that uses `setTimeout`, you can switch that code over to this wrapper instead,
     * and then mock the wrapper. We can't entirely mock `setTimeout` because that seems to break VSCode.
     */
    static setTimeout(callback: (...args: any[]) => void, ms: number, ...args: any[]): NodeJS.Timeout;
}
/**
 * Gets the appropriately formatted title for a journal note, given the full
 * note name and the configured date format.
 * @param noteName note name like 'daily.journal.2021.01.01'
 * @param dateFormat - should be gotten from Journal Config's 'dateFormat'
 * @returns formatted title, or undefined if the journal title could not be parsed.
 */
export declare function getJournalTitle(noteName: string, dateFormat: string): string | undefined;
/**
 * Helper function to get a subset of NoteChangeEntry's matching a
 * particular status from an array
 * @param entries
 * @param status
 * @returns
 */
export declare function extractNoteChangeEntriesByType(entries: NoteChangeEntry[], status: "create" | "delete" | "update"): NoteChangeEntry[];
export declare function extractNoteChangeEntryCountByType(entries: NoteChangeEntry[], status: "create" | "delete" | "update"): number;
export declare function extractNoteChangeEntryCounts(entries: NoteChangeEntry[]): {
    createdCount: number;
    deletedCount: number;
    updatedCount: number;
};
export declare function globMatch(patterns: string[] | string, fname: string): boolean;
