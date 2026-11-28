import type { Plugin } from "unified";
type PluginOpts = {
    hierarchyDisplayTitle?: string;
    hierarchyDisplay?: boolean;
};
/** Adds the "Children", "Tags", and "Footnotes" items to the end of the note. Also renders footnotes. */
declare const plugin: Plugin;
export { plugin as hierarchies };
export { PluginOpts as HierarchiesOpts };
