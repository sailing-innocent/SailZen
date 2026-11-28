import { DNoteRefLink, DVault, SailConfig, NoteDicts, NotePropsMeta, OptionalExceptFor, ProcFlavor } from "@saili/common-all";
import { Processor } from "unified";
import { BacklinkOpts } from "./remark/backlinksHover";
import { SailPubOpts } from "./remark/sailPub";
import { WikiLinksOpts } from "./remark/wikiLinks";
import { SailASTDest, UnistNode } from "./types";
import { Parent } from "unist";
export { ProcFlavor };
/**
 * What mode a processor should run in
 */
export declare enum ProcMode {
    /**
     * Expect no properties from {@link ProcDataFullV5} when running the processor
     */
    NO_DATA = "NO_DATA",
    /**
     * Expect all properties from {@link ProcDataFullV5} when running the processor
     */
    FULL = "all data",
    /**
     * Running processor in import mode. Notes don't exist. Used for import pods like {@link MarkdownPod}
     * where notes don't exist in the engine prior to import.
     */
    IMPORT = "IMPORT"
}
/**
 * Options for how processor should function
 */
export type ProcOptsV5 = {
    /**
     * Determines what information is passed in to `Proc`
     */
    mode: ProcMode;
    /**
     * Don't attach compiler if `parseOnly`
     */
    parseOnly?: boolean;
    /**
     * Are we using specific variant of processor
     */
    flavor?: ProcFlavor;
};
/**
 * Data to initialize the processor
 */
export type ProcDataFullOptsV5 = {
    vault: DVault;
    fname: string;
    dest: SailASTDest;
    config: SailConfig;
    vaults?: DVault[];
    /**
     * Check to see if we are in a note reference.
     */
    insideNoteRef?: boolean;
    /**
     * frontmatter variables exposed for substitution
     */
    fm?: any;
    wikiLinksOpts?: WikiLinksOpts;
    publishOpts?: SailPubOpts;
    backlinkHoverOpts?: BacklinkOpts;
    wsRoot?: string;
    noteToRender: NotePropsMeta;
    noteCacheForRenderDict?: NoteDicts;
};
/**
 * Data from the processor
 */
export type ProcDataFullV5 = {
    vault: DVault;
    fname: string;
    dest: SailASTDest;
    wsRoot: string;
    vaults: DVault[];
    config: SailConfig;
    insideNoteRef?: boolean;
    fm?: any;
    /**
     * Keep track of current note ref level
     */
    noteRefLvl: number;
    noteToRender: NotePropsMeta;
    noteCacheForRenderDict?: NoteDicts;
};
export type NoteRefId = {
    id: string;
    link: DNoteRefLink;
};
export type SerializedNoteRef = {
    node: UnistNode;
    refId: NoteRefId;
    prettyHAST: any;
};
type RefCache = Record<string, SerializedNoteRef>;
export declare class MDUtilsV5 {
    static getRefsRoot: (wsRoot: string) => string;
    /**
     * Write ref
     * @param param1
     */
    static cacheRefId({ refId, mdast, prettyHAST, }: {
        refId: NoteRefId;
        mdast: Parent;
        prettyHAST: any;
    }): void;
    static clearRefCache(): void;
    static getRefCache(): RefCache;
    static getProcOpts(proc: Processor): ProcOptsV5;
    static getProcData(proc: Processor): ProcDataFullV5;
    static setNoteRefLvl(proc: Processor, lvl: number): Processor<undefined, undefined, undefined, undefined, undefined>;
    static setProcData(proc: Processor, opts: Partial<ProcDataFullV5>): Processor<undefined, undefined, undefined, undefined, undefined>;
    static setProcOpts(proc: Processor, opts: ProcOptsV5): Processor<undefined, undefined, undefined, undefined, undefined>;
    static isV5Active(proc: Processor): boolean;
    static shouldApplyPublishingRules(proc: Processor): boolean;
    static getFM(opts: {
        note: NotePropsMeta;
    }): any;
    /**
     * Used for processing a Sail markdown note
     */
    static _procRemark(opts: ProcOptsV5, data: OptionalExceptFor<ProcDataFullOptsV5, "config">): any;
    static _procRehype(opts: ProcOptsV5, data: Omit<ProcDataFullOptsV5, "dest">): any;
    static procRemarkFull(data: ProcDataFullOptsV5, opts?: {
        mode?: ProcMode;
        flavor?: ProcFlavor;
    }): any;
    /**
     * Parse Sail Markdown Note. No compiler is attached.
     * @param opts
     * @param data
     * @returns
     */
    static procRemarkParse(opts: ProcOptsV5, data: OptionalExceptFor<ProcDataFullOptsV5, "config">): any;
    /**
     *
     * Warning! When using a no-data parser, any user configuration will not be
     * available. Avoid using it unless you are sure that the user configuration
     * has no effect on what you are doing.
     */
    static procRemarkParseNoData(opts: Omit<ProcOptsV5, "mode" | "parseOnly">, data: Partial<ProcDataFullOptsV5> & {
        dest: SailASTDest;
    }): any;
    static procRemarkParseFull(opts: Omit<ProcOptsV5, "mode" | "parseOnly">, data: ProcDataFullOptsV5): any;
    static procRehypeFull(data: Omit<ProcDataFullOptsV5, "dest">, opts?: {
        flavor?: ProcFlavor;
    }): any;
}
export declare const getRefId: ({ link, id }: {
    link: DNoteRefLink;
    id: string;
}) => string;
