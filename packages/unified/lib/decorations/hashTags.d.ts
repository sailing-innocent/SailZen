import { SailConfig, NoteProps, Position, ReducedDEngine } from "@saili/common-all";
import { HashTag } from "../types";
import { Decorator } from "./utils";
import { DecorationWikilink } from "./wikilinks";
export type DecorationHashTag = DecorationWikilink & {
    color?: string;
};
export declare function isDecorationHashTag(decoration: DecorationWikilink): decoration is DecorationHashTag;
export declare const decorateHashTag: Decorator<HashTag, DecorationHashTag>;
export declare function decorateTag({ fname, engine, position, lineOffset, config, note, }: {
    fname: string;
    engine: ReducedDEngine;
    position: Position;
    lineOffset?: number;
    config: SailConfig;
    note?: NoteProps;
}): Promise<{
    errors: import("@saili/common-all").ISailError[];
    decorations: (import("@saili/common-all").Decoration & {
        type: import("@saili/common-all").DECORATION_TYPES.wikiLink | import("@saili/common-all").DECORATION_TYPES.brokenWikilink;
    } & {
        color?: string;
    })[];
}>;
