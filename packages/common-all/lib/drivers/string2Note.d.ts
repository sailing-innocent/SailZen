import { DVault } from "../types/DVault";
/**
 * Shared note parsing helper used by server-side file utilities.
 * @param calculateHash - when set, add `contentHash` property to the note
 *  Default: false
 * @returns
 */
export declare function string2Note({ content, fname, vault, calculateHash, }: {
    content: string;
    fname: string;
    vault: DVault;
    calculateHash?: boolean;
}): import("..").DNodeProps;
