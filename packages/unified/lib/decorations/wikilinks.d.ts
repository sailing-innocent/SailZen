import { DNoteRefLink, DVault, ISailError, NoteProps, NotePropsMeta, ReducedDEngine } from "@saili/common-all";
import { WikiLinkNoteV4 } from "../types";
import { DecorationTaskNote } from "./taskNotes";
import { Decoration, DECORATION_TYPES, Decorator } from "./utils";
export type DecorationWikilink = WikiLinkDecorator | NoteRefDecorator;
export type WikiLinkDecorator = Decoration & {
    type: DECORATION_TYPES.wikiLink | DECORATION_TYPES.brokenWikilink;
};
export type NoteRefDecorator = Required<Decoration<{
    link: DNoteRefLink;
    noteMeta?: NotePropsMeta;
}>> & {
    type: DECORATION_TYPES.noteRef | DECORATION_TYPES.brokenNoteRef;
};
export type DecorationAlias = Decoration & {
    type: DECORATION_TYPES.alias;
};
type DecorationsForDecorateWikilink = DecorationWikilink | DecorationAlias | DecorationTaskNote;
export declare const decorateWikilink: Decorator<WikiLinkNoteV4, DecorationsForDecorateWikilink>;
export declare function linkedNoteType({ fname, anchorStart, anchorEnd, vaultName, note, engine, vaults, }: {
    fname?: string;
    anchorStart?: string;
    anchorEnd?: string;
    vaultName?: string;
    note?: NoteProps;
    engine: ReducedDEngine;
    vaults: DVault[];
}): Promise<{
    type: DECORATION_TYPES.brokenWikilink | DECORATION_TYPES.wikiLink;
    noteMeta?: NotePropsMeta;
    errors: ISailError[];
}>;
export {};
