import { DLink, DLoc, Position } from "./types";
export declare class DLinkUtils {
    static isEquivalent(linkA: DLink, linkB: DLink): boolean;
    static isDLocEquivalent(locA: DLoc | undefined, locB: DLoc | undefined): boolean;
    static isPositionEquivalent(posA: Position | undefined, posB: Position | undefined): boolean;
}
