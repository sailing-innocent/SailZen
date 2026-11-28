import { Image } from "mdast";
import type { Transformer, Processor } from "unified";
type PluginOpts = {};
/** Makes the `.url` of the given image note a full path. */
export declare function makeImageUrlFullPath({ proc, node, }: {
    proc: Processor;
    node: Image;
}): void;
export declare function sailHoverPreview(this: Processor, _opts?: PluginOpts): Transformer;
export { PluginOpts as SailPreviewOpts };
