import { ALIAS_NAME, SailError, DEngineClient, DLink, DNodeProps, DNoteAnchor, DNoteAnchorBasic, DNoteAnchorPositioned, DNoteLink, DNoteLoc, DNoteRefLink, DNoteRefLinkRaw, DVault, getSlugger, SailConfig, LINK_CONTENTS, LINK_NAME, NoteBlock, NoteChangeEntry, NoteDicts, NoteProps, NotePropsMeta, Position, ReducedDEngine } from "@saili/common-all";
import type { Code, FootnoteDefinition, FrontmatterContent, Heading, HTML, Image, Link, List, Paragraph, Table, TableCell, TableRow, Text, YAML } from "mdast";
import * as mdastBuilder from "mdast-builder";
import { Processor } from "unified";
import { Node, Parent } from "unist";
import { visit } from "unist-util-visit";
import { VFile } from "vfile";
import { Anchor, SailASTDest, SailASTTypes, ExtendedImage, HashTag, NoteRefNoteV4, ZDocTag, WikiLinkNoteV4, WikiLinkProps } from "../types";
export { select, selectAll } from "unist-util-select";
export { mdastBuilder };
export { visit };
export { LINK_CONTENTS, LINK_NAME, ALIAS_NAME };
export declare function addError(proc: Processor, err: SailError): void;
export declare function getNoteOrError(notes: NoteProps[], hint: any): {
    error: SailError | undefined;
    note: undefined | NoteProps;
};
export type LinkFilter = {
    loc?: Partial<DNoteLoc>;
};
export type ParseLinkV2Resp = {
    alias?: string;
    value: string;
    anchorHeader?: string;
    vaultName?: string;
    sameFile: false;
} | {
    alias?: string;
    value?: string;
    anchorHeader: string;
    vaultName?: string;
    sameFile: true;
};
export declare function hashTag2WikiLinkNoteV4(hashtag: HashTag): WikiLinkNoteV4;
export declare function zdocTag2WikiLinkNoteV4(zdocTag: ZDocTag): WikiLinkNoteV4;
export declare function frontmatterTag2WikiLinkNoteV4(tag: string, useHashSymbol?: boolean): WikiLinkNoteV4;
export declare class LinkUtils {
    static astType2DLinkType(type: SailASTTypes): DLink["type"];
    static dlink2DNoteLink(link: DLink): DNoteLink;
    /**
     * Get links from note body while maintaining existing backlinks
     */
    static findLinks({ note, engine, type, config, filter, }: {
        note: NoteProps;
        engine: ReducedDEngine;
        config: SailConfig;
        filter?: LinkFilter;
        type: "regular" | "candidate";
    }): Promise<DLink[]>;
    /**
     * Get all links from the note body
     * Currently, just look for wiki links
     *
     * @param opts.filter - {type, loc
     *
     * - type: filter by {@link SailASTTypes}
     * - loc: filter by {@link DLoc}
     */
    static findLinksFromBody({ note, config, filter, }: {
        note: NoteProps;
        config: SailConfig;
        filter?: LinkFilter;
    }): DLink[];
    static findHashTags({ links }: {
        links: DLink[];
    }): DLink[];
    static isAlias(link: string): boolean;
    static hasFilter(link: string): boolean;
    static parseAliasLink(link: string): {
        alias: string;
        value: string;
    };
    /** Either value or anchorHeader will always be present if the function did not
     *  return null. A missing value means that the file containing this link is
     *  the value.
     *
     *  if `explicitAlias` is false, non-existent alias will be
     *  implicitly assumed to be the value of the link.
     */
    static parseLinkV2(opts: {
        linkString: string;
        explicitAlias?: boolean;
    }): ParseLinkV2Resp | null;
    static getNotesFromWikiLinks(opts: {
        activeNote: DNodeProps;
        wikiLinks: ParseLinkV2Resp[];
        engine: DEngineClient;
    }): Promise<NoteProps[]>;
    static parseLink(linkMatch: string): WikiLinkProps;
    static parseNoteRefRaw(ref: string): DNoteRefLinkRaw;
    static parseNoteRef(ref: string): DNoteRefLink;
    static renderNoteLink({ link, dest, }: {
        link: DNoteLink;
        dest: SailASTDest;
    }): string;
    /**
     * Given a note, updates old link to new link.
     * If you are calling this on a note multiple times,
     * You need to start from the last link in the body
     * Because each updateLink call will shift the location of
     * every element in the note body that comes after
     * the link you update
     *
     * @param note the note that contains link to update
     * @param oldLink the old link that needs to be updated
     * @param newLink new link
     * @returns
     */
    static updateLink({ note, oldLink, newLink, }: {
        note: NoteProps;
        oldLink: DNoteLink;
        newLink: DNoteLink;
    }): string;
    static isHashtagLink(link: DNoteLoc): link is DNoteLoc & {
        alias: string;
    };
    static isZDocTagLink(link: DNoteLoc): link is DNoteLoc & {
        alias: string;
    };
    static findLinkCandidates({ note, engine, config, }: {
        note: NoteProps;
        engine: ReducedDEngine;
        config: SailConfig;
    }): Promise<DLink[]>;
    /**
     *  Use this version during engine initialization on the engine side, where
     *  the entire set of noteDicts is available. This version uses local data so
     *  it's much faster.
     * @param param0
     * @returns
     */
    static findLinkCandidatesSync({ note, noteDicts, config, }: {
        note: NoteProps;
        noteDicts: NoteDicts;
        config: SailConfig;
    }): DLink[];
    static hasVaultPrefix(link: DLink): boolean;
    /**
     * Given a source string, extract all wikilinks within the source.
     *
     * @param source string to extract wikilinks from
     */
    static extractWikiLinks(source: string): ParseLinkV2Resp[];
    /**
     * Given an array of links that need to be updated,
     * and a note that contains the links,
     * update all links in given array so that they point to
     * the destination note.
     *
     * returns note change entries
     */
    static updateLinksInNote(opts: {
        linksToUpdate: DNoteLink[];
        note: NoteProps;
        destNote: NoteProps;
        engine: DEngineClient;
    }): Promise<import("@saili/common-all").WriteNoteResp>;
}
export type GetAnchorsResp = {
    [index: string]: DNoteAnchorPositioned;
};
export declare class AnchorUtils {
    /** Given a header, finds the text of that header, including any wikilinks or hashtags that are included in the header.
     *
     * For example, for the header `## Foo [[Bar|bar]] and #baz`, the text should be `Foo Bar and #baz`.
     */
    static headerText(header: Heading): string;
    /** Given a header, finds the range of text that marks the contents of the header.
     *
     * For example, for the header `## Foo [[Bar|bar]] and #baz`, the range will start after `## ` and end at the end of the line.
     */
    static headerTextPosition(header: Heading): Position;
    /** Given a *parsed* anchor node, returns the anchor id ("header" or "^block" and positioned anchor object for it. */
    static anchorNode2anchor(node: Anchor, slugger: ReturnType<typeof getSlugger>): [string, DNoteAnchorPositioned] | undefined;
    static findAnchors(opts: {
        note: NoteProps;
    }): GetAnchorsResp;
    static anchor2string(anchor: DNoteAnchor | DNoteAnchorBasic): string;
    static string2anchor(anchor: string): DNoteAnchorBasic;
}
export declare class RemarkUtils {
    /**
     * Use this to [[Get the line offset of the frontmatter|sail://sail.docs/pkg.plugin-core.dev.cook#get-the-line-offset-of-the-frontmatter]]
     * Given a string representation of a Sail note,
     * return the position of the line right after the frontmatter.
     * @param fileText file content string to traverse
     * @returns position in parsed file content right after the frontmatter
     */
    static getNodePositionPastFrontmatter(fileText: string): Position | undefined;
    static bumpHeadings(root: Parent, baseDepth: number): void;
    static findAnchors(content: string): Anchor[];
    static isHeading(node: Node, text: string, depth?: number): node is Heading;
    static isRoot(node: Node): node is Parent;
    static isParent(node: Node): node is Parent;
    static isParagraph(node: Node): node is Paragraph;
    static isTable(node: Node): node is Table;
    static isTableRow(node: Node): node is TableRow;
    static isTableCell(node: Node): node is TableCell;
    static isList(node: Node): node is List;
    static isNoteRefV2(node: Node): node is NoteRefNoteV4;
    static isImage(node: Node): node is Image;
    static isExtendedImage(node: Node): node is ExtendedImage;
    static isText(node: Node): node is Text;
    static isLink(node: Node): node is Link;
    static isWikiLink(node: Node): node is WikiLinkNoteV4;
    static isFootnoteDefinition(node: Node): node is FootnoteDefinition;
    static isFrontmatter(node: Node): node is FrontmatterContent;
    static isHTML(node: Node): node is HTML;
    static isCode(node: Node): node is Code;
    static isYAML(node: Node): node is YAML;
    static isHashTag(node: Node): node is HashTag;
    static isZDocTag(node: Node): node is ZDocTag;
    static isNodeWithPosition<N extends Node>(node: N): node is N & {
        position: Position;
    };
    static convertLinksFromDotNotation(note: NoteProps, changes: NoteChangeEntry[]): (this: Processor) => (tree: Node, _vfile: VFile) => void;
    static convertWikiLinkToNoteUrl(note: NoteProps, changes: NoteChangeEntry[], engine: DEngineClient, sailConfig: SailConfig): (this: Processor) => (tree: Node, _vfile: VFile) => Promise<void>;
    static h1ToTitle(note: NoteProps, changes: NoteChangeEntry[]): (this: Processor) => (tree: Node, _vfile: VFile) => void;
    static h1ToH2(note: NoteProps, changes: NoteChangeEntry[]): (this: Processor) => (tree: Node, _vfile: VFile) => void;
    /**
     * Recursively check if two given node has identical children.
     * At each level _position_ is omitted as this can change if
     * you are comparing from two different trees.
     * @param a first {@link Node} to compare
     * @param b second {@link Node} to compare
     * @returns boolean
     */
    static hasIdenticalChildren: (a: Node, b: Node) => boolean;
    /**
     * Given a markdown AST and a target heading node,
     * Find all the node that belongs under the heading.
     * This will extract all nodes until it hits the next heading
     * with the same depth of the target heading.
     * @param tree Abstract syntax tree
     * @param startHeaderDepth Heading to target
     * @returns nodes to extract
     */
    static extractHeaderBlock(tree: Node, startHeaderDepth: number, startHeaderIndex: number, stopAtFirstHeader?: boolean): Node[];
    /** Extract all blocks from the note which could be referenced by a block anchor.
     *
     * If those blocks already have anchors (or if they are a header), this will also find that anchor.
     *
     * @param note The note from which blocks will be extracted.
     */
    static extractBlocks({ note, config, }: {
        note: NoteProps;
        config: SailConfig;
    }): Promise<NoteBlock[]>;
    static extractFootnoteDefs(root: Node): FootnoteDefinition[];
    /**
     * Extract frontmatter tags from note
     * @param body
     * @returns
     */
    static extractFMTags(body: string): import("yaml-unist-parser").Literal[];
    static getNoteUrl(opts: {
        config: SailConfig;
        note: NotePropsMeta;
        vault: DVault;
        urlRoot?: string;
        anchor?: string;
    }): string;
}
