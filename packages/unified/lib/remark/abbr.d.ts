import type { Plugin } from "unified";
/**
 * Plugin options for remark-abbr replacement
 */
type PluginOpts = {
    /** When set to true, the first occurrence of each abbreviation is expanded in place */
    expandFirst?: boolean;
};
declare const plugin: Plugin<[PluginOpts?]>;
export { plugin as abbrPlugin };
export type { PluginOpts as AbbrOpts };
