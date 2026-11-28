import { NoteProps } from "@saili/common-all";
import type { Transformer, Processor } from "unified";
type PluginOpts = {
    noteIndex: NoteProps;
};
/**
 * Used when publishing
 * Rewrite index note
 */
declare function plugin(this: Processor, opts: PluginOpts): Transformer;
export { plugin as publishSite };
export { PluginOpts as PublishSiteOpts };
