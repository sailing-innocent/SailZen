// TODO: remove this disable once we deprecate old site config.
/* eslint-disable camelcase */
import GithubSlugger from "github-slugger";
import _ from "lodash";
import { minimatch } from "minimatch";
import path from "path";
import normalizePath from "normalize-path";
import semver from "semver";
import { DateTime, LruCache, VaultUtils } from "..";
import { parse, z, schemaForType } from "../parse";
import { COLORS_LIST } from "../colors";
import SparkMD5 from "spark-md5";
import { CompatUtils, CONFIG_TO_MINIMUM_COMPAT_MAPPING, ERROR_SEVERITY, } from "../constants";
import { SAIL_CONFIG } from "../constants/configs/sailConfig";
import { SailError, ErrorMessages } from "../error";
import { genDefaultPublishingConfig, publishingSchema, SearchMode, } from "../types/configs/publishing/publishing";
import { isWebUri } from "../util/regex";
import { genDefaultCommandConfig, genDefaultPreviewConfig, genDefaultWorkspaceConfig, } from "../types/configs";
export { ok, Ok, err, Err, Result, okAsync, errAsync, ResultAsync, fromThrowable, fromPromise, fromSafePromise, } from "neverthrow";
export * from "./lookup";
export * from "./publishUtils";
export * from "./vscode-utils";
/**
 * Sail utilities
 */
export class DUtils {
    static minimatch = minimatch;
    static semver = semver;
}
export const getSlugger = () => {
    return new GithubSlugger();
};
/**
 * determine if given parameter is numeric
 * https://stackoverflow.com/questions/18082/validate-decimal-numbers-in-javascript-isnumeric/1830844#1830844
 * @param n
 * @returns boolean
 */
export const isNumeric = (n) => {
    // eslint-disable-next-line no-restricted-globals, radix
    return !isNaN(parseInt(n)) && isFinite(n);
};
export function isBlockAnchor(anchor) {
    // not undefined, not an empty string, and the first character is ^
    return !!anchor && anchor[0] === "^";
}
export function isLineAnchor(anchor) {
    // not undefined, not an empty string, and the first character is L, and is followed by numbers
    return !!anchor && /L\d+/.test(anchor);
}
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
export function isNotUndefined(t) {
    return !_.isUndefined(t);
}
export function isNotNull(t) {
    return !_.isNull(t);
}
/**
 * Check if the value u is a falsy value.
 */
export function isFalsy(u) {
    if (_.isBoolean(u)) {
        return u === false;
    }
    return _.some([_.isUndefined(u), _.isEmpty(u), _.isNull(u)]);
}
/** Calculates a basic integer hash for the given string.
 *
 * This is very unsafe, do not rely on this for anything where collisions are bad.
 *
 * Adapted from https://github.com/darkskyapp/string-hash.
 * Originally released under CC0 1.0 Universal (CC0 1.0) Public Domain Dedication.
 */
function basicStringHash(text) {
    // eslint-disable-next-line no-bitwise
    return (
    // eslint-disable-next-line no-bitwise
    _.reduce(text, (prev, curr) => {
        return prev + curr.charCodeAt(0);
    }, 5381) >>>
        // JavaScript does bitwise operations (like XOR, above) on 32-bit signed
        // integers. Since we want the results to be always positive, convert the
        // signed int to an unsigned by doing an unsigned bitshift.
        0);
}
/** Given a string, return a random color as a HTML color code.
 *
 * The same string will always generate the same color, and different strings will get different random colors.
 */
export function randomColor(text) {
    return COLORS_LIST[basicStringHash(text) % COLORS_LIST.length];
}
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
export function makeColorTranslucent(color, translucency) {
    let match = color.match(/^#[\dA-Fa-f]{6}$/);
    if (match)
        return `${color}${(translucency * 255).toString(16)}`;
    match = color.match(/^((rgb|hsl)\( *[\d.]+ *, *[\d.]+%? *, *[\d.]+%? *)\)$/);
    if (match)
        return `${match[1]}, ${translucency})`;
    match = color.match(/^((rgb|hsl)\( *[\d.]+ *[\d.]+%? *[\d.]+%? *)\)$/);
    if (match)
        return `${match[1]} / ${translucency})`;
    return color;
}
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
export function memoize({ fn, keyFn = (...args) => args[0].toString(), shouldUpdate = () => false, maxCache = 64, }) {
    const wrapped = function memoize(...args) {
        const key = keyFn(...args);
        let value = wrapped.cache.get(key);
        if (value === undefined || shouldUpdate(value, ...args)) {
            wrapped.cache.drop(key);
            value = fn(...args);
            wrapped.cache.set(key, value);
        }
        return value;
    };
    wrapped.cache = new LruCache({ maxItems: maxCache });
    return wrapped;
}
export class FIFOQueue {
    _internalQueue = [];
    constructor(init) {
        if (init)
            this._internalQueue = init;
    }
    enqueue(item) {
        this._internalQueue.push(item);
    }
    enqueueAll(items) {
        for (const item of items)
            this.enqueue(item);
    }
    dequeue() {
        return this._internalQueue.shift();
    }
    get length() {
        return this._internalQueue.length;
    }
}
/** Similar to lodash `_.groupBy`, except not limited to string keys. */
export function groupBy(collection, iteratee) {
    const map = new Map();
    collection.forEach((value, index) => {
        const key = iteratee(value, index);
        let group = map.get(key);
        if (group === undefined) {
            group = [];
            map.set(key, group);
        }
        group.push(value);
    });
    return map;
}
export function mapValues(inMap, applyFn) {
    const outMap = new Map();
    for (const [key, value] of inMap.entries()) {
        outMap.set(key, applyFn(value));
    }
    return outMap;
}
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
export function throttleAsyncUntilComplete({ fn, keyFn, timeout, }) {
    const lastStarted = new Map();
    return async (...args) => {
        const key = keyFn(...args);
        const last = lastStarted.get(key);
        if (last === undefined ||
            (timeout !== undefined && Date.now() - last > timeout)) {
            // Function was never run with this input before or it timed out, re-run it
            lastStarted.set(key, Date.now());
            let out;
            try {
                out = await fn(...args);
            }
            finally {
                lastStarted.delete(key);
            }
            return out;
        }
        return undefined;
    };
}
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
export function debounceAsyncUntilComplete({ fn, keyFn, timeout, trailing, }) {
    const states = new Map();
    const debouncedFn = async (...args) => {
        const key = keyFn(...args);
        const state = states.get(key);
        if (state === "timeout" || state === "trailing") {
            // Another execution is already scheduled
            return;
        }
        else if (state === "execute" && trailing) {
            // Currently executing, and configured for a trailing execution
            states.set(key, "trailing");
        }
        else {
            // Not currently executing or scheduled, schedule now
            states.set(key, "timeout");
            setTimeout(async () => {
                // timeout done, start executing
                states.set(key, "execute");
                try {
                    await fn(...args);
                }
                finally {
                    const lastState = states.get(key);
                    // execution complete, mark as not executing
                    states.delete(key);
                    if (lastState === "trailing") {
                        // but if we had a trailing execution scheduled, do that
                        debouncedFn(...args);
                    }
                }
            }, timeout);
        }
    };
    return { debouncedFn, states };
}
export function genHash(contents) {
    return SparkMD5.hash(contents); // OR raw hash (binary string)
}
export class TagUtils {
    /** Removes `oldTag` from the frontmatter tags of `note` and replaces it with `newTag`, if any. */
    static replaceTag({ note, oldTag, newTag, }) {
        if (_.isUndefined(note.tags) || _.isString(note.tags)) {
            note.tags = newTag;
        }
        else {
            const index = _.findIndex(note.tags, (tag) => tag === oldTag);
            if (newTag) {
                if (index >= 0) {
                    note.tags[index] = newTag;
                }
                else {
                    // Weird, can't find the old tag. Add the new one anyway.
                    note.tags.push(newTag);
                }
            }
            else {
                _.pull(note.tags, oldTag);
            }
        }
    }
}
export class ConfigUtils {
    static genDefaultConfig() {
        const common = {
            dev: {
                enablePreviewV2: true,
            },
        };
        return {
            version: 5,
            ...common,
            commands: genDefaultCommandConfig(),
            workspace: genDefaultWorkspaceConfig(),
            preview: genDefaultPreviewConfig(),
            publishing: genDefaultPublishingConfig(),
        };
    }
    /**
     * This is different from {@link genDefaultConfig}
     * as it includes updated settings that we don't want to set as
     * defaults for backward compatibility reasons
     */
    static genLatestConfig(defaults) {
        const common = {
            dev: {
                enablePreviewV2: true,
            },
        };
        const mergedPublishingConfig = _.merge(genDefaultPublishingConfig(), {
            searchMode: SearchMode.SEARCH,
        });
        return _.merge({
            version: 5,
            ...common,
            commands: genDefaultCommandConfig(),
            workspace: { ...genDefaultWorkspaceConfig() },
            preview: genDefaultPreviewConfig(),
            publishing: mergedPublishingConfig,
        }, defaults);
    }
    // get
    static getProp(config, key) {
        const defaultConfig = ConfigUtils.genDefaultConfig();
        const configWithDefaults = _.defaultsDeep(config, defaultConfig);
        return configWithDefaults[key];
    }
    static getCommands(config) {
        return ConfigUtils.getProp(config, "commands");
    }
    static getWorkspace(config) {
        return ConfigUtils.getProp(config, "workspace");
    }
    static getPreview(config) {
        const out = ConfigUtils.getProp(config, "preview");
        // FIXME: for some reason, this can return undefined when run in context of chrome in `sail-plugin-views`
        if (_.isUndefined(out)) {
            return ConfigUtils.genDefaultConfig().preview;
        }
        return out;
    }
    static getPublishing(config) {
        return ConfigUtils.getProp(config, "publishing");
    }
    static getVaults(config) {
        return ConfigUtils.getWorkspace(config).vaults;
    }
    static getHooks(config) {
        return ConfigUtils.getWorkspace(config).hooks;
    }
    static getJournal(config) {
        return ConfigUtils.getWorkspace(config).journal;
    }
    static getScratch(config) {
        return ConfigUtils.getWorkspace(config).scratch;
    }
    static getTask(config) {
        return ConfigUtils.getWorkspace(config).task;
    }
    static getLookup(config) {
        return ConfigUtils.getCommands(config).lookup;
    }
    static getEnableFMTitle(config, shouldApplyPublishRules) {
        const publishRule = ConfigUtils.getPublishing(config).enableFMTitle;
        return shouldApplyPublishRules
            ? publishRule
            : ConfigUtils.getPreview(config).enableFMTitle;
    }
    static getEnableNoteTitleForLink(config, shouldApplyPublishRules) {
        const publishRule = ConfigUtils.getPublishing(config).enableNoteTitleForLink;
        return shouldApplyPublishRules
            ? publishRule
            : ConfigUtils.getPreview(config).enableNoteTitleForLink;
    }
    static getEnableKatex(config, shouldApplyPublishRules) {
        const publishRule = ConfigUtils.getPublishing(config).enableKatex;
        return shouldApplyPublishRules
            ? publishRule
            : ConfigUtils.getPreview(config).enableKatex;
    }
    static getHierarchyConfig(config) {
        return ConfigUtils.getPublishing(config).hierarchy;
    }
    static getGithubConfig(config) {
        return ConfigUtils.getPublishing(config).github;
    }
    static getGiscusConfig(config) {
        return ConfigUtils.getPublishing(config).giscus;
    }
    static getLogo(config) {
        return ConfigUtils.getPublishing(config).logoPath;
    }
    static getAssetsPrefix(config) {
        return ConfigUtils.getPublishing(config).assetsPrefix;
    }
    static getEnableRandomlyColoredTags(config) {
        return ConfigUtils.getPublishing(config).enableRandomlyColoredTags;
    }
    static getEnableFrontmatterTags(opts) {
        const { config, shouldApplyPublishRules } = opts;
        const publishRule = ConfigUtils.getPublishing(config).enableFrontmatterTags;
        return shouldApplyPublishRules
            ? publishRule
            : ConfigUtils.getPreview(config).enableFrontmatterTags;
    }
    static getEnableHashesForFMTags(opts) {
        const { config, shouldApplyPublishRules } = opts;
        const publishRule = ConfigUtils.getPublishing(config).enableHashesForFMTags;
        return shouldApplyPublishRules
            ? publishRule
            : ConfigUtils.getPreview(config).enableHashesForFMTags;
    }
    static getEnablePrettlyLinks(config) {
        return ConfigUtils.getPublishing(config).enablePrettyLinks;
    }
    static getGATracking(config) {
        return ConfigUtils.getPublishing(config).ga?.tracking;
    }
    static getSiteLastModified(config) {
        return ConfigUtils.getPublishing(config).enableSiteLastModified;
    }
    static getSiteLogoUrl(config) {
        const assetsPrefix = ConfigUtils.getAssetsPrefix(config);
        const logo = ConfigUtils.getLogo(config);
        if (logo === undefined)
            return undefined;
        // Let's allow logos that are hosted off-site/in subdomains by passing in a full URL
        if (isWebUri(logo))
            return logo;
        // Otherwise, this has to be an asset. It can't be anywhere else because of backwards compatibility.
        const logoBase = path.basename(logo); // Why just discard the rest of logo? Because that's what code used to do and I'm preserving backwards compatibility
        if (assetsPrefix) {
            const initialSlash = assetsPrefix.startsWith("/") ? "" : "/";
            return `${initialSlash}${assetsPrefix}/assets/${logoBase}`;
        }
        return `/assets/${logoBase}`;
    }
    static getEnablePrettyRefs(config, opts) {
        const override = opts?.note?.config?.global?.enablePrettyRefs;
        if (override !== undefined)
            return override;
        const publishRule = ConfigUtils.getPublishing(config).enablePrettyRefs;
        return opts?.shouldApplyPublishRules
            ? publishRule
            : ConfigUtils.getPreview(config).enablePrettyRefs;
    }
    /**
     * NOTE: _config currently doesn't have a `global` object. We're keeping it here
     * to make using the API easier when we do add it
     */
    static getEnableChildLinks(_config, opts) {
        if (opts &&
            opts.note &&
            opts.note.config &&
            opts.note.config.global &&
            !_.isUndefined(opts.note.config.global.enableChildLinks)) {
            return opts.note.config.global.enableChildLinks;
        }
        return true;
    }
    static getEnableBackLinks(_config, opts) {
        // check if note has override. takes precedence
        if (opts &&
            opts.note &&
            opts.note.config &&
            opts.note.config.global &&
            _.isBoolean(opts.note.config.global.enableBackLinks)) {
            return opts.note.config.global.enableBackLinks;
        }
        // check config value, if enableBacklinks set, then use value set
        const publishConfig = ConfigUtils.getPublishing(_config);
        if (ConfigUtils.isSailPublishingConfig(publishConfig) &&
            opts?.shouldApplyPublishingRules) {
            if (_.isBoolean(publishConfig.enableBackLinks)) {
                return publishConfig.enableBackLinks;
            }
        }
        return true;
    }
    static getHierarchyDisplayConfigForPublishing(config) {
        const hierarchyDisplay = ConfigUtils.getPublishing(config).enableHierarchyDisplay;
        const hierarchyDisplayTitle = ConfigUtils.getPublishing(config).hierarchyDisplayTitle;
        return { hierarchyDisplay, hierarchyDisplayTitle };
    }
    static getNonNoteLinkAnchorType(config) {
        return (this.getCommands(config).copyNoteLink.nonNoteFile?.anchorType || "block");
    }
    static getAliasMode(config) {
        return this.getCommands(config).copyNoteLink.aliasMode;
    }
    static getVersion(config) {
        return config.version;
    }
    static getSearchMode(config) {
        const defaultMode = ConfigUtils.getPublishing(config).searchMode;
        return defaultMode || SearchMode.LOOKUP;
    }
    // set
    static setProp(config, key, value) {
        _.set(config, key, value);
    }
    static setCommandsProp(config, key, value) {
        const path = `commands.${key}`;
        _.set(config, path, value);
    }
    static setWorkspaceProp(config, key, value) {
        const path = `workspace.${key}`;
        _.set(config, path, value);
    }
    static setPublishProp(config, key, value) {
        const path = `publishing.${key}`;
        _.set(config, path, value);
    }
    /**
     * Set properties under the publishing.github namaspace (v5+ config)
     */
    static setGithubProp(config, key, value) {
        const path = `publishing.github.${key}`;
        _.set(config, path, value);
    }
    static isSailPublishingConfig(config) {
        return _.has(config, "enableBackLinks");
    }
    static overridePublishingConfig(config, value) {
        return {
            ...config,
            publishing: value,
        };
    }
    static unsetProp(config, key) {
        _.unset(config, key);
    }
    static unsetPublishProp(config, key) {
        const path = `publishing.${key}`;
        _.unset(config, path);
    }
    static setDuplicateNoteBehavior(config, value) {
        ConfigUtils.setPublishProp(config, "duplicateNoteBehavior", value);
    }
    static unsetDuplicateNoteBehavior(config) {
        ConfigUtils.unsetPublishProp(config, "duplicateNoteBehavior");
    }
    static setVaults(config, value) {
        ConfigUtils.setWorkspaceProp(config, "vaults", value);
    }
    /** Finds the matching vault in the config, and uses the callback to update it. */
    static updateVault(config, vaultToUpdate, updateCb) {
        ConfigUtils.setVaults(config, ConfigUtils.getVaults(config).map((configVault) => {
            if (!VaultUtils.isEqualV2(vaultToUpdate, configVault))
                return configVault;
            return updateCb(configVault);
        }));
    }
    static setNoteLookupProps(config, key, value) {
        const path = `commands.lookup.note.${key}`;
        _.set(config, path, value);
    }
    static setJournalProps(config, key, value) {
        const path = `workspace.journal.${key}`;
        _.set(config, path, value);
    }
    static setScratchProps(config, key, value) {
        const path = `workspace.scratch.${key}`;
        _.set(config, path, value);
    }
    static setHooks(config, value) {
        ConfigUtils.setWorkspaceProp(config, "hooks", value);
    }
    static setPreviewProps(config, key, value) {
        const path = `preview.${key}`;
        _.set(config, path, value);
    }
    static setNonNoteLinkAnchorType(config, value) {
        _.set(config, "commands.copyNoteLink.nonNoteFile.anchorType", value);
    }
    static setAliasMode(config, aliasMode) {
        _.set(config, "commands.copyNoteLink.aliasMode", aliasMode);
    }
    static configIsValid(opts) {
        const { clientVersion, configVersion } = opts;
        if (_.isUndefined(configVersion)) {
            throw new SailError({
                message: "Cannot determine config version. Please make sure the field 'version' is present and correct",
                severity: ERROR_SEVERITY.FATAL,
            });
        }
        const minCompatClientVersion = CONFIG_TO_MINIMUM_COMPAT_MAPPING[configVersion].clientVersion;
        if (_.isUndefined(minCompatClientVersion)) {
            throw new SailError({
                message: ErrorMessages.formatShouldNeverOccurMsg("Cannot find minimum compatible client version."),
                severity: ERROR_SEVERITY.FATAL,
            });
        }
        const minCompatConfigVersion = _.findLastKey(CONFIG_TO_MINIMUM_COMPAT_MAPPING, (ent) => {
            return semver.lte(ent.clientVersion, clientVersion);
        });
        if (_.isUndefined(minCompatConfigVersion)) {
            throw new SailError({
                message: ErrorMessages.formatShouldNeverOccurMsg("cannot find minimum compatible config version."),
                severity: ERROR_SEVERITY.FATAL,
            });
        }
        const clientVersionCompatible = semver.lte(minCompatClientVersion, clientVersion);
        const isSoftMapping = CompatUtils.isSoftMapping({
            configVersion: Number(minCompatConfigVersion),
        });
        const configVersionCompatible = Number(minCompatConfigVersion) <= configVersion;
        const isValid = clientVersionCompatible && configVersionCompatible;
        if (!isValid) {
            const reason = clientVersionCompatible ? "config" : "client";
            return {
                isValid,
                reason,
                isSoftMapping,
                minCompatClientVersion,
                minCompatConfigVersion,
            };
        }
        else {
            return { isValid, minCompatClientVersion, minCompatConfigVersion };
        }
    }
    static detectMissingDefaults(opts) {
        const { config } = opts;
        const configDeepCopy = _.cloneDeep(config);
        let { defaultConfig } = opts;
        if (defaultConfig === undefined) {
            defaultConfig = ConfigUtils.genDefaultConfig();
        }
        const backfilledConfig = _.defaultsDeep(config, defaultConfig);
        return {
            needsBackfill: !_.isEqual(backfilledConfig, configDeepCopy),
            backfilledConfig,
        };
    }
    static detectDeprecatedConfigs(opts) {
        const { config, deprecatedPaths } = opts;
        const foundDeprecatedPaths = deprecatedPaths.filter((path) => _.has(config, path));
        if (foundDeprecatedPaths.length === 0) {
            return [];
        }
        return foundDeprecatedPaths;
    }
    static getConfigDescription = (conf) => {
        return _.get(SAIL_CONFIG, conf)?.desc;
    };
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
    static flattenConfigObject(opts) {
        const { obj, omitPaths } = opts;
        const objDeepCopy = _.cloneDeep(obj);
        if (omitPaths && omitPaths.length > 0) {
            omitPaths.forEach((path) => {
                _.unset(objDeepCopy, path);
            });
        }
        const accumulator = [];
        const flattenToPathValuePairs = (opts) => {
            const { obj, parent } = opts;
            const entries = _.entries(obj);
            entries.forEach((entry) => {
                const [key, value] = entry;
                const pathSoFar = `${parent ? `${parent}.` : ""}`;
                if (_.isObject(value) && !_.isArrayLikeObject(value)) {
                    flattenToPathValuePairs({
                        obj: _.get(obj, key),
                        parent: `${pathSoFar}${key}`,
                    });
                }
                else if (_.isArrayLikeObject(value)) {
                    accumulator.push({
                        path: `${pathSoFar}${key}`,
                        value: JSON.stringify(value),
                    });
                }
                else {
                    accumulator.push({
                        path: `${pathSoFar}${key}`,
                        value,
                    });
                }
            });
        };
        flattenToPathValuePairs({ obj: objDeepCopy });
        return accumulator;
    }
    /**
     * Given a config, find the difference compared to the default.
     *
     * This is used to track changes from the default during activation.
     */
    static findDifference(opts) {
        const { config } = opts;
        const defaultConfig = ConfigUtils.genDefaultConfig();
        const omitPaths = [
            "workspace.workspaces",
            "workspace.vaults",
            "workspace.seeds",
            "dev",
        ];
        const flatConfigObject = ConfigUtils.flattenConfigObject({
            obj: config,
            omitPaths,
        });
        const flatDefaultConfigObject = ConfigUtils.flattenConfigObject({
            obj: defaultConfig,
            omitPaths,
        });
        const diff = _.differenceWith(flatConfigObject, flatDefaultConfigObject, _.isEqual);
        return diff;
    }
    /**
     * Parses an unkown input into a SailConfig
     * @param input
     */
    static parse(input) {
        const schema = schemaForType()(z
            .object({
            version: z.number(),
            dev: z.object({}).passthrough().optional(), // TODO SailDevConfig;
            commands: z.object({}).passthrough(), // TODO SailCommandConfig;
            workspace: z.object({}).passthrough(), // TODO SailWorkspaceConfig;
            preview: z.object({}).passthrough(), // TODO SailPreviewConfig;
            publishing: publishingSchema,
            global: z.object({}).passthrough().optional(), // TODO SailGlobalConfig;
        })
            .passthrough());
        return parse(schema, input, "Invalid Sail Config").map((value) => {
            // TODO remove once all properties are defined in the schema, because that the parse will have set all default values for us already.
            return _.defaultsDeep(value, ConfigUtils.genDefaultConfig());
        });
    }
}
/**
 * Make name safe for sail
 * @param name
 * @param opts
 */
export function cleanName(name) {
    name = name
        .replace(new RegExp(_.escapeRegExp(path.sep), "g"), ".")
        .toLocaleLowerCase();
    name = name.replace(/ /g, "-");
    return name;
}
/**
 * Given a path on any platform, convert it to a unix style path. Avoid using this with absolute paths.
 */
export function normalizeUnixPath(fsPath) {
    return path.posix
        ? path.posix.normalize(fsPath.replace(/\\/g, "/"))
        : normalizePath(fsPath); // `path.posix` might be not available depending on your build system. For example at the time of writing `sail-plugin-views` does not implement a `posix` property.
}
/** Wrapper(s) for easier testing, to wrap functions where we don't want to mock the global function. */
export class Wrap {
    /** A useless wrapper around `setTimeout`. Useful for testing.
     *
     * If you are testing code that uses `setTimeout`, you can switch that code over to this wrapper instead,
     * and then mock the wrapper. We can't entirely mock `setTimeout` because that seems to break VSCode.
     */
    static setTimeout(callback, ms, ...args) {
        return setTimeout(callback, ms, ...args);
    }
}
/**
 * Gets the appropriately formatted title for a journal note, given the full
 * note name and the configured date format.
 * @param noteName note name like 'daily.journal.2021.01.01'
 * @param dateFormat - should be gotten from Journal Config's 'dateFormat'
 * @returns formatted title, or undefined if the journal title could not be parsed.
 */
export function getJournalTitle(noteName, dateFormat) {
    let title = noteName.split(".");
    while (title.length > 0) {
        const attemptedParse = DateTime.fromFormat(title.join("."), dateFormat);
        if (attemptedParse.isValid) {
            return title.join("-");
        }
        title = title.length > 1 ? title.slice(1) : [];
    }
    return undefined;
}
/**
 * Helper function to get a subset of NoteChangeEntry's matching a
 * particular status from an array
 * @param entries
 * @param status
 * @returns
 */
export function extractNoteChangeEntriesByType(entries, status) {
    return entries.filter((entry) => entry.status === status);
}
export function extractNoteChangeEntryCountByType(entries, status) {
    return extractNoteChangeEntriesByType(entries, status).length;
}
export function extractNoteChangeEntryCounts(entries) {
    return {
        createdCount: extractNoteChangeEntryCountByType(entries, "create"),
        deletedCount: extractNoteChangeEntryCountByType(entries, "delete"),
        updatedCount: extractNoteChangeEntryCountByType(entries, "update"),
    };
}
export function globMatch(patterns, fname) {
    if (_.isString(patterns)) {
        return minimatch(fname, patterns);
    }
    return _.some(patterns, (pattern) => minimatch(fname, pattern));
}
//# sourceMappingURL=index.js.map