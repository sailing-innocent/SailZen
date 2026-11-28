import type { Plugin } from "unified";
type PluginOpts = {
    wrapper: string;
    selector: string;
    fallback?: boolean;
};
declare const plugin: Plugin<[PluginOpts]>;
export { plugin as wrap };
