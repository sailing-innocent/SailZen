import type { Transformer, Processor } from "unified";
import { Position } from "unist";
/**
 * Options for the backlinks hover transformer. If using
 * ProcFlavor.BACKLINKS_PANEL_HOVER, then this must be set.
 */
export type BacklinkOpts = {
    /**
     * How many lines before and after the backlink to show in the hover
     */
    linesOfContext: number;
    /**
     * The location of the backlink text
     */
    location: Position;
};
/**
 * Unified processor for rendering text in the backlinks hover control. This
 * processor returns a transformer that does the following:
 * 1. Highlights the backlink text
 * 2. Changes the backlink node away from a wikilink/noteref to prevent the
 *    backlink text from being altered
 * 3. Adds contextual " --- line # ---" information
 * 4. Removes all elements that lie beyond the contextual lines limit of the
 *    backlink
 * @param this
 * @param _opts
 * @returns
 */
export declare function backlinksHover(this: Processor, _opts?: BacklinkOpts): Transformer;
