import { DLink, NotePropsMeta } from "./types";
type BackLink = Omit<DLink, "type"> & {
    type: "backlink";
};
export declare class BacklinkUtils {
    /**
     * Create backlink out of link if it references another note (denoted by presence of link.to field)
     *
     * @param link Original link to create backlink out of
     * @returns backlink or none if not applicable
     */
    static createFromDLink(link: DLink): BackLink | undefined;
    /** Adds a backlink by mutating the 'note' argument in place.
     * Check if backlink already exists before pushing
     *
     *  @param note note that the link is pointing to. (mutated)
     *  @param link backlink to add. */
    static addBacklinkInPlace({ note, backlink, }: {
        note: NotePropsMeta;
        backlink: BackLink;
    }): void;
    /**
     * Remove backlink from note. If note does not contain that backlink, do nothing.
     * Mutates note in place
     *
     * @param note Note to update backlinks for.
     * @param backlink Backlink to remove
     */
    static removeBacklinkInPlace({ note, backlink, }: {
        note: NotePropsMeta;
        backlink: BackLink;
    }): void;
}
export {};
