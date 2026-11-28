import { SailError, DNoteRefLink } from "@saili/common-all";
import { Heading } from "mdast";
import type { Plugin, Processor } from "unified";
import { Node, Parent } from "unist";
import { SailASTNode } from "../types";
import { ParentWithIndex } from "../utils";
import { WikiLinksOpts } from "./wikiLinks";
type PluginOpts = CompilerOpts;
type CompilerOpts = {
    prettyRefs?: boolean;
    wikiLinkOpts?: WikiLinksOpts;
};
type ConvertNoteRefOpts = {
    link: DNoteRefLink;
    proc: Processor;
    compilerOpts: CompilerOpts;
};
export declare class NoteRefUtils {
    static dnodeRefLink2String(link: DNoteRefLink): string;
}
export declare function isBeginBlockAnchorId(anchorId: string): anchorId is "begin";
export declare function isEndBlockAnchorId(anchorId: string): anchorId is "end";
declare const plugin: Plugin;
/**
 * This exists because {@link sailPub} converts note refs using the AST
 */
export declare function convertNoteRefToHAST(opts: ConvertNoteRefOpts & {
    procOpts: any;
}): {
    error: SailError | undefined;
    data: Parent[] | undefined;
};
export declare function prepareNoteRefIndices<T>({ anchorStart, anchorEnd, bodyAST, makeErrorData, }: {
    anchorStart?: string;
    anchorEnd?: string;
    bodyAST: SailASTNode;
    makeErrorData: (msg: string) => T;
}): {
    start: FindAnchorResult;
    end: FindAnchorResult;
    data: T | null;
    error: any;
};
type FindAnchorResult = {
    type: "block";
    index: number;
    anchorType?: "block";
    node?: Node;
} | {
    type: "header";
    index: number;
    anchorType?: "header";
    node?: Heading;
} | {
    type: "block-begin";
    index: number;
    node: Node;
} | {
    type: "block-end";
    index: number;
    node: Node;
} | {
    type: "list";
    index: number;
    ancestors: ParentWithIndex[];
    anchorType?: "block";
} | {
    type: "none";
    index: number;
} | null;
export { plugin as noteRefsV2 };
export { PluginOpts as NoteRefsOptsV2 };
