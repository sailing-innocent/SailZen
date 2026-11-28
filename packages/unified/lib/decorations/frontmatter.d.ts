import { FrontmatterContent } from "mdast";
import { DecorationHashTag } from "./hashTags";
import { Decoration, DECORATION_TYPES, Decorator } from "./utils";
export type DecorationTimestamp = Decoration & {
    type: DECORATION_TYPES.timestamp;
    timestamp: number;
};
type DecorationsForDecorateFrontmatter = DecorationTimestamp | DecorationHashTag;
export declare const decorateFrontmatter: Decorator<FrontmatterContent, DecorationsForDecorateFrontmatter>;
export {};
