import { SailError, SailErrorProps, ISailError } from "../error";
import { DVault } from "./DVault";
import { NoteProps } from "./foundation";
/** The error codes of errors that can occur during engine init. */
export declare enum EngineInitErrorType {
    DUPLICATE_NOTE_ID = "duplicate note id"
}
/** A duplicate note ID error.
 *
 * Note IDs must be unique, duplicate note IDs can cause issues in many parts of
 * Sail. This error occurs when a duplicate note ID is detected during engine
 * init. It's non-fatal because most of Sail will still function after this
 * error.
 */
export declare class DuplicateNoteError extends SailError<EngineInitErrorType.DUPLICATE_NOTE_ID> {
    constructor(opts: Omit<SailErrorProps<EngineInitErrorType.DUPLICATE_NOTE_ID>, "name" | "message" | "severity"> & {
        noteA: NoteProps;
        noteB: NoteProps;
    });
    noteA: {
        fname: string;
        vault: DVault;
    };
    noteB: {
        fname: string;
        vault: DVault;
    };
    static isDuplicateNoteError(error: ISailError<any>): error is DuplicateNoteError;
}
