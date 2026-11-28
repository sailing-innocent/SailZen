import { SailError, DEngineClient, Disposable, DLink, DVault, NoteChangeEntry, NoteDicts, NoteProps, ValidateFnameResp } from "@saili/common-all";
import { createDisposableLogger } from "@saili/common-server";
export declare enum DoctorActionsEnum {
    FIX_FRONTMATTER = "fixFrontmatter",
    H1_TO_TITLE = "h1ToTitle",
    HI_TO_H2 = "h1ToH2",
    REMOVE_STUBS = "removeStubs",
    CREATE_MISSING_LINKED_NOTES = "createMissingLinkedNotes",
    REGENERATE_NOTE_ID = "regenerateNoteId",
    FIND_BROKEN_LINKS = "findBrokenLinks",
    FIX_REMOTE_VAULTS = "fixRemoteVaults",
    ADD_MISSING_DEFAULT_CONFIGS = "addMissingDefaultConfigs",
    REMOVE_DEPRECATED_CONFIGS = "removeDeprecatedConfigs",
    FIX_SELF_CONTAINED_VAULT_CONFIG = "fixSelfContainedVaultsInConfig",
    FIX_INVALID_FILENAMES = "fixInvalidFileNames"
}
export type DoctorServiceOpts = {
    action: DoctorActionsEnum;
    query?: string;
    candidates?: NoteProps[];
    limit?: number;
    dryRun?: boolean;
    exit?: boolean;
    quiet?: boolean;
    engine: DEngineClient;
    podId?: string;
    hierarchy?: string;
    vault?: DVault | string;
};
/** DoctorService is a disposable, you **must** dispose instances you create
 * otherwise you risk leaking file descriptors which may lead to crashes. */
export declare class DoctorService implements Disposable {
    L: ReturnType<typeof createDisposableLogger>["logger"];
    private loggerDispose;
    private print;
    constructor(opts?: {
        printFunc?: Function;
    });
    dispose(): void;
    findBrokenLinks(note: NoteProps, noteDicts: NoteDicts, engine: DEngineClient): DLink[];
    getBrokenLinkDestinations(notes: NoteProps[], engine: DEngineClient): NoteProps[];
    findMisconfiguredSelfContainedVaults(wsRoot: string, vaults: DVault[]): Promise<DVault[]>;
    executeDoctorActions(opts: DoctorServiceOpts): Promise<{
        exit: boolean;
        error: SailError<import("@saili/common-all").StatusCodes | undefined>;
        resp?: undefined;
    } | {
        exit: boolean;
        error?: undefined;
        resp?: undefined;
    } | {
        exit: boolean;
        resp: any;
        error?: undefined;
    }>;
    /** Returns the path for the backup if it was able to create one, or a SailError if one occurred during backup. */
    createBackup(wsRoot: string, backupInfix: string): Promise<string | SailError>;
    findInvalidFileNames(opts: {
        notes: NoteProps[];
        noteDicts: NoteDicts;
    }): {
        canRename: {
            cleanedFname: string;
            canRename: boolean;
            note: NoteProps;
            resp: ValidateFnameResp;
        }[];
        cantRename: {
            cleanedFname: string;
            canRename: boolean;
            note: NoteProps;
            resp: ValidateFnameResp;
        }[];
        stats: {
            numEmptyHierarchy: number;
            numIllegalCharacter: number;
            numLeadingOrTrailingWhitespace: number;
        };
    };
    fixInvalidFileNames(opts: {
        canRename: {
            cleanedFname: string;
            canRename: boolean;
            note: NoteProps;
            resp: ValidateFnameResp;
        }[];
        engine: DEngineClient;
    }): Promise<NoteChangeEntry[]>;
}
