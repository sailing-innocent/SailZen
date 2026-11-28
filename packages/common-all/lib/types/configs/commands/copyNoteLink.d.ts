/** "line" uses line numbers (`L23`), "block" inserts block anchors (`^xf1g...`). "prompt" means prompt the user to select one. */
export type NonNoteFileLinkAnchorType = "line" | "block" | "prompt";
/**
 * Namespace for configuring {@link CopyNoteLinkCommand}
 */
export type CopyNoteLinkConfig = {
    nonNoteFile?: {
        anchorType?: NonNoteFileLinkAnchorType;
    };
    aliasMode: "none" | "title";
};
export declare function genDefaultCopyNoteLinkConfig(): CopyNoteLinkConfig;
