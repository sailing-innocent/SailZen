import { DNoteRefLink, getSlugger, NoteProps, NotesCacheEntry, ReducedDEngine } from "@saili/common-all";
import { WSMeta } from "../types";
export * from "./engineUtils";
/**
 * Details:
 * - trim white space, remove `#`, handle `*` and slug
 */
export declare function normalizev2(text: string, slugger: ReturnType<typeof getSlugger>): string;
/**
 * stringify a note ref link
 * @param opts
 * @returns
 */
export declare function refLink2Stringv2(opts: {
    link: DNoteRefLink;
    useVaultPrefix?: boolean;
    rawAnchors?: boolean;
}): string;
export declare function getWSMetaFilePath({ wsRoot }: {
    wsRoot: string;
}): string;
export declare function openWSMetaFile({ fpath }: {
    fpath: string;
}): WSMeta;
export declare function writeWSMetaFile({ fpath, data, }: {
    fpath: string;
    data: WSMeta;
}): void;
export declare function parseSailRef(ref: string): {
    direction: "to";
    link: DNoteRefLink | undefined;
};
export declare function parseFileLink(ref: string): DNoteRefLink;
export declare const matchRefMarker: (txt: string) => RegExpMatchArray | null;
export declare function createCacheEntry(opts: {
    noteProps: NoteProps;
    hash: string;
}): NotesCacheEntry;
export declare const getCachePath: (vpath: string) => string;
export declare const removeCache: (vpath: string) => Promise<void> | undefined;
/**
 @deprecated - remove after version 0.76
 * @param doc
 * @returns
 */
export declare function stripLocalOnlyTags(doc: string): string;
export declare class HierarchyUtils {
    /**
     * Get children of current note
     * @param opts.skipLevels: how many levels to skip for child
     * @returns
     */
    static getChildren: (opts: {
        skipLevels: number;
        note: NoteProps;
        engine: ReducedDEngine;
    }) => Promise<NoteProps[]>;
}
