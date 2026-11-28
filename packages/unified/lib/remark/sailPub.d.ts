import type { Processor, Transformer } from "unified";
import { NoteRefsOptsV2 } from "./noteRefs";
type PluginOpts = NoteRefsOptsV2 & {
    assetsPrefix?: string;
    insertTitle?: boolean;
    /**
     * Don't publish pages that are dis-allowd by sail.yml
     */
    transformNoPublish?: boolean;
    /** Don't display randomly generated colors for tags, only display color if it's explicitly set by the user. */
    noRandomlyColoredTags?: boolean;
};
declare function plugin(this: Processor, opts?: PluginOpts): Transformer;
export { plugin as sailPub };
export { PluginOpts as SailPubOpts };
