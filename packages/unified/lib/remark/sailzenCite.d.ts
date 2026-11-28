import type { Plugin } from "unified";
/**
 * Remark plugin for SailZen ::cite[keys] directive.
 *
 * Parses inline citations like:
 *   ::cite[foo, bar]
 *   ::cite[ foo , bar ]
 *
 * And produces a sailzenCite AST node.
 */
export declare const CITE_REGEX: RegExp;
type PluginOpts = {};
declare const plugin: Plugin<[PluginOpts?]>;
export { plugin as sailzenCite };
