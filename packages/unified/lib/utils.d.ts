import { getSlugger, SailConfig, NoteProps } from "@saili/common-all";
import { Heading } from "mdast";
import { Node, Parent } from "unist";
import { SailASTNode } from "./types";
export declare const renderFromNote: (opts: {
    note: NoteProps;
}) => string;
export type ParentWithIndex = {
    ancestor: Parent;
    index: number;
};
type VisitorParentsIndices = ({ node, index, ancestors, }: {
    node: Node;
    index: number;
    ancestors: ParentWithIndex[];
}) => boolean | undefined | "skip";
export type FindHeaderAnchor = {
    type: "header";
    index: number;
    node?: Heading;
    anchorType?: "header";
};
/** Contains functions that help dealing with MarkDown Abstract Syntax Trees. */
export declare class MdastUtils {
    static genMDMsg(msg: string): Parent;
    static genMDErrorMsg(msg: string): Parent;
    static findHeader({ nodes, match, slugger, }: {
        nodes: SailASTNode["children"];
        match: string | Heading;
        slugger?: ReturnType<typeof getSlugger>;
    }): FindHeaderAnchor | null;
    /** Find the index of the list element for which the predicate `fn` returns true.
     *
     * @returns The index where the element was found, -1 otherwise.
     */
    static findIndex<T>(array: T[], fn: (node: T, index: number) => boolean): number;
    /** A simplified and adapted version of visitParents from unist-utils-visit-parents, that also keeps track of indices of the ancestors as well.
     *
     * The limitations are:
     * * `test`, if used, can only be a string representing the type of the node that you want to visit
     * * Adding or removing siblings is undefined behavior
     * Please modify this function to add support for these if needed.
     */
    static visitParentsIndices({ nodes, test, visitor, }: {
        nodes: Node[];
        test?: string;
        visitor: VisitorParentsIndices;
    }): void;
    /** Similar to `unist-utils-visit`, but allows async visitors.
     *
     * Children are visited in-order, not concurrently.
     *
     * @param test Use an empty list to visit all nodes, otherwise specify node types to be visited.
     * @param visitor Similar to `unist-util-visit`, returning true or undefined continues traversal, false stops traversal, and "skip" skips the children of that node.
     *
     * Depth-first pre-order traversal, same as `unist-util-visits`.
     */
    static visitAsync(tree: Node, test: string[], visitor: (node: Node) => void | undefined | boolean | "skip" | Promise<void | undefined | boolean | "skip">): Promise<void>;
    static matchHeading(node: Node, matchText: string, opts: {
        depth?: number;
        slugger: ReturnType<typeof getSlugger>;
    }): boolean;
}
export declare class PublishUtils {
    static getAbsUrlForAsset(opts: {
        suffix?: string;
        config: SailConfig;
    }): string;
    static getSiteUrl: (config: SailConfig) => string | undefined;
}
export {};
