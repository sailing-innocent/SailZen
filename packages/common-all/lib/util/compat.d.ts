import { Point, Position, VSPosition, VSRange } from "../types";
export type PointOffset = {
    line?: number;
    column?: number;
};
/** Convert a `Point` from a parsed remark node to a `vscode.Poisition`
 *
 * @param point The point to convert.
 * @param offset When converting the point, shift it by this much.
 * @returns The converted Position, shifted by `offset` if provided.
 */
export declare function point2VSCodePosition(point: Point, offset?: PointOffset): VSPosition;
/** Convert a `Position` from a parsed remark node to a `vscode.Range`
 *
 * @param position The position to convert.
 * @returns The converted Range.
 */
export declare function position2VSCodeRange(position: Position, offset?: PointOffset): VSRange;
/** Similar to VSCode's `Document.getRange`, except that it works with strings. */
export declare function getTextRange(text: string, range: VSRange): string;
/**
 * Similar to doing a `delete` on an `editor.edit()`, except it works with strings.
 */
export declare function deleteTextRange(text: string, range: VSRange): string;
export declare function newRange(startLine: number, startCharacter: number, endLine: number, endCharacter: number): VSRange;
export declare function offsetRange(range: VSRange, offset: PointOffset): VSRange;
