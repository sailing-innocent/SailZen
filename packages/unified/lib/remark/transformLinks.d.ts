import { DNoteLoc } from "@saili/common-all";
import type { Transformer, Processor } from "unified";
type PluginOpts = {
    from: DNoteLoc;
    to: DNoteLoc;
};
/**
 * Used from renaming wikilinks
 */
declare function plugin(this: Processor, opts: PluginOpts): Transformer;
export { plugin as transformLinks };
export { PluginOpts as TransformLinkOpts };
