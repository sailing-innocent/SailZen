import { ERROR_SEVERITY } from "../constants";
import { SailError } from "../error";
import { VaultUtils } from "../vault";
/** The error codes of errors that can occur during engine init. */
export var EngineInitErrorType;
(function (EngineInitErrorType) {
    EngineInitErrorType["DUPLICATE_NOTE_ID"] = "duplicate note id";
})(EngineInitErrorType || (EngineInitErrorType = {}));
/** A duplicate note ID error.
 *
 * Note IDs must be unique, duplicate note IDs can cause issues in many parts of
 * Sail. This error occurs when a duplicate note ID is detected during engine
 * init. It's non-fatal because most of Sail will still function after this
 * error.
 */
export class DuplicateNoteError extends SailError {
    constructor(opts) {
        super({
            ...opts,
            severity: ERROR_SEVERITY.MINOR,
            message: `Notes ${opts.noteA.fname} in ${VaultUtils.getName(opts.noteA.vault)} and ${opts.noteB.fname} in ${VaultUtils.getName(opts.noteB.vault)} have duplicate IDs.`,
            code: EngineInitErrorType.DUPLICATE_NOTE_ID,
        });
        this.noteA = {
            fname: opts.noteA.fname,
            vault: opts.noteA.vault,
        };
        this.noteB = {
            fname: opts.noteB.fname,
            vault: opts.noteB.vault,
        };
    }
    noteA;
    noteB;
    static isDuplicateNoteError(error) {
        return error.code === EngineInitErrorType.DUPLICATE_NOTE_ID;
    }
}
//# sourceMappingURL=errorTypes.js.map