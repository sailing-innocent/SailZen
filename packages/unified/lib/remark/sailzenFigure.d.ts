import type { Plugin } from "unified";
/**
 * Remark plugin for SailZen ::figure[caption](src){opts} directive.
 *
 * Parses inline figures like:
 *   ::figure[Overview](fig_overview){width=0.8\textwidth}
 *   ::figure[Caption](image.png)
 *
 * And produces a sailzenFigure AST node.
 */
export declare const FIGURE_REGEX: RegExp;
type PluginOpts = {};
declare const plugin: Plugin<[PluginOpts?]>;
export { plugin as sailzenFigure };
