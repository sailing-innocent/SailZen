export * from "./frontend";
export * from "./views";
export * from "./lookup";
export * from "./configs/compat";
export { ReasonPhrases, StatusCodes, getReasonPhrase, getStatusCode, } from "http-status-codes";
export declare enum ThemeType {
    LIGHT = "light",
    DARK = "dark"
}
export declare enum ThemeTarget {
    PRISM = "PRISM"
}
export declare const CONSTANTS: {
    ROOT_PATH: string;
    ALL_QUERY: string;
    SAIL_WS_NAME: string;
    SAIL_SERVER_PORT: string;
    SAIL_WS_META: string;
    SAIL_CONFIG_FILE: string;
    SAIL_LOCAL_CONFIG_FILE: string;
    SAIL_SEED_CONFIG: string;
    SRC_DELIMITER: string;
    SAIL_DELIMETER: string;
    SAIL_USER_FILE: string;
    SAIL_CACHE_FILE: string;
    SAIL_ID: string;
    SAIL_NO_TELEMETRY: string;
    SAIL_TELEMETRY: string;
    SAIL_HOOKS_BASE: string;
    SAIL_USER_NOTE_TRAITS_BASE: string;
    SAIL_LOCAL_SITE_PORT: number;
    /**
     * Initial version for first installaion
     */
    SAIL_INIT_VERSION: string;
    /** Default for the `maxNoteLength` config. */
    SAIL_DEFAULT_MAX_NOTE_LENGTH: number;
    /** The file containing the custom theme CSS. Located at the workspace root. */
    CUSTOM_THEME_CSS: string;
};
export declare const FOLDERS: {
    /** The folder where the vault dependencies are stored. */
    DEPENDENCIES: string;
    /** The subfolder of {@link FOLDERS.DEPENDENCIES} where local vaults are stored. */
    LOCAL_DEPENDENCY: string;
    /** The folder where the notes of the vault are stored. */
    NOTES: string;
    /** The folder where the assets are stored, this will be under {@link FOLDERS.NOTES}. */
    ASSETS: string;
    /** The system-wide folder where Sail stores metadata and other system-wide files. */
    SAIL_SYSTEM_ROOT: string;
    /** The folder where telemetry payloads that will be sent during next run are temporarily saved. Under {@link FOLDERS.SAIL_SYSTEM_ROOT}. */
    SAVED_TELEMETRY: string;
};
export declare enum ERROR_STATUS {
    BACKUP_FAILED = "backup_failed",
    NODE_EXISTS = "node_exists",
    NO_SCHEMA_FOUND = "no_schema_found",
    NO_ROOT_SCHEMA_FOUND = "no_root_schema_found",
    MISSING_SCHEMA = "missing_schema",
    NO_ROOT_NOTE_FOUND = "no_root_note_found",
    BAD_PARSE_FOR_SCHEMA = "bad_parse_for_schema",
    NO_PARENT_FOR_NOTE = "no_parent_for_note",
    CANT_DELETE_ROOT = "no_delete_root_node",
    BAD_PARSE_FOR_NOTE = "bad_parse_for_note",
    ENGINE_NOT_SET = "no_engine_set",
    NOT_AUTHORIZED = "not_authorized",
    DOES_NOT_EXIST = "does_not_exist_error",
    INVALID_CONFIG = "invalid_config",
    INVALID_STATE = "invalid_state",
    UNKNOWN = "unknown",
    CONTENT_NOT_FOUND = "content_not_found",
    WRITE_FAILED = "write_failed",
    DELETE_FAILED = "delete_failed",
    RENAME_FAILED = "rename_failed"
}
export declare enum USER_MESSAGES {
    UNKNOWN = "unknown"
}
/**
 * Labels whether error is recoverable or not
 */
export declare enum ERROR_SEVERITY {
    MINOR = "minor",
    FATAL = "fatal"
}
export declare enum RESERVED_KEYS {
    GIT_NOTE_PATH = "gitNotePath",
    GIT_NO_LINK = "gitNoLink"
}
export declare const TAGS_HIERARCHY_BASE = "tags";
/** Notes under this hierarchy are considered tags, for example `${TAGS_HIERARCHY}foo` is a tag note. */
export declare const TAGS_HIERARCHY = "tags.";
export declare const TAGS_PREFIX = "#";
export declare const TAGS_POSTFIX = "";
export declare const ZDOCS_HIERARCHY_BASE = "source.zdoc";
export declare const ZDOCS_HIERARCHY = "source.zdoc.";
export declare const ZDOCS_TAG_PREFIX = "\\cite{";
export declare const ZDOCS_TAG_PREFIX_REGEX = "\\\\cite\\{";
export declare const ZDOCS_TAG_SUFFIX = "}";
export declare const ZDOCS_TAG_SUFFIX_REGEX = "\\}";
export declare const SPECIAL_TAGS: {
    base: string;
    prefix: string;
    postfix: string;
}[];
export type VaultRemoteSource = "local" | "remote";
export declare enum SAIL_EMOJIS {
    SEEDLING = "\uD83C\uDF31",
    OKAY = "\u2705",
    NOT_OKAY = "\u274E"
}
export declare enum SAIL_VSCODE_CONFIG_KEYS {
    ENABLE_SELF_CONTAINED_VAULTS_WORKSPACE = "sail.enableSelfContainedVaultWorkspace"
}
/**
 * Keys to a global state store. Global here means across a single user's
 * different access platforms.
 */
export declare enum GLOBAL_STATE_KEYS {
    ANONYMOUS_ID = "telemetry.anonymousId"
}
