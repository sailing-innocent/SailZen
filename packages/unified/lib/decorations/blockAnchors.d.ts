import { BlockAnchor } from "../types";
import { Decoration, DECORATION_TYPES, Decorator } from "./utils";
export type DecorationBlockAnchor = Decoration & {
    type: DECORATION_TYPES.blockAnchor;
};
export declare const decorateBlockAnchor: Decorator<BlockAnchor, DecorationBlockAnchor>;
