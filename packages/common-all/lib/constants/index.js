export * from "./frontend";
export * from "./views";
export * from "./lookup";
export * from "./configs/compat";
export { ReasonPhrases, StatusCodes, getReasonPhrase, getStatusCode, } from "http-status-codes";
const ROOT_PATH = "/doc/root";
export var ThemeType;
(function (ThemeType) {
    ThemeType["LIGHT"] = "light";
    ThemeType["DARK"] = "dark";
})(ThemeType || (ThemeType = {}));
export var ThemeTarget;
(function (ThemeTarget) {
    ThemeTarget["PRISM"] = "PRISM";
})(ThemeTarget || (ThemeTarget = {}));
export const CONSTANTS = {
    ROOT_PATH,
    ALL_QUERY: "**/*",
    SAIL_WS_NAME: "sail.code-workspace",
    SAIL_SERVER_PORT: ".sail.port",
    SAIL_WS_META: ".sail.ws",
    SAIL_CONFIG_FILE: "sail.yml",
    SAIL_LOCAL_CONFIG_FILE: "sailrc.yml",
    SAIL_SEED_CONFIG: "seed.yml",
    SRC_DELIMITER: "src://",
    SAIL_DELIMETER: "sail://",
    SAIL_USER_FILE: ".sail.user",
    SAIL_CACHE_FILE: ".sail.cache.json",
    SAIL_ID: ".sail.uuid",
    SAIL_NO_TELEMETRY: ".sail.no-telemetry",
    SAIL_TELEMETRY: ".sail.telemetry",
    SAIL_HOOKS_BASE: "hooks",
    SAIL_USER_NOTE_TRAITS_BASE: "noteTraits",
    SAIL_LOCAL_SITE_PORT: 8080,
    /**
     * Initial version for first installaion
     */
    SAIL_INIT_VERSION: "0.0.0",
    /** Default for the `maxNoteLength` config. */
    SAIL_DEFAULT_MAX_NOTE_LENGTH: 204800,
    /** The file containing the custom theme CSS. Located at the workspace root. */
    CUSTOM_THEME_CSS: "custom.css",
};
export const FOLDERS = {
    /** The folder where the vault dependencies are stored. */
    DEPENDENCIES: "dependencies",
    /** The subfolder of {@link FOLDERS.DEPENDENCIES} where local vaults are stored. */
    LOCAL_DEPENDENCY: "localhost",
    /** The folder where the notes of the vault are stored. */
    NOTES: "notes",
    /** The folder where the assets are stored, this will be under {@link FOLDERS.NOTES}. */
    ASSETS: "assets",
    /** The system-wide folder where Sail stores metadata and other system-wide files. */
    SAIL_SYSTEM_ROOT: ".sail",
    /** The folder where telemetry payloads that will be sent during next run are temporarily saved. Under {@link FOLDERS.SAIL_SYSTEM_ROOT}. */
    SAVED_TELEMETRY: "saved-telemetry",
};
export var ERROR_STATUS;
(function (ERROR_STATUS) {
    ERROR_STATUS["BACKUP_FAILED"] = "backup_failed";
    ERROR_STATUS["NODE_EXISTS"] = "node_exists";
    ERROR_STATUS["NO_SCHEMA_FOUND"] = "no_schema_found";
    ERROR_STATUS["NO_ROOT_SCHEMA_FOUND"] = "no_root_schema_found";
    ERROR_STATUS["MISSING_SCHEMA"] = "missing_schema";
    ERROR_STATUS["NO_ROOT_NOTE_FOUND"] = "no_root_note_found";
    ERROR_STATUS["BAD_PARSE_FOR_SCHEMA"] = "bad_parse_for_schema";
    ERROR_STATUS["NO_PARENT_FOR_NOTE"] = "no_parent_for_note";
    ERROR_STATUS["CANT_DELETE_ROOT"] = "no_delete_root_node";
    // --- 400, client errors
    // Bucket
    ERROR_STATUS["BAD_PARSE_FOR_NOTE"] = "bad_parse_for_note";
    ERROR_STATUS["ENGINE_NOT_SET"] = "no_engine_set";
    // 401
    ERROR_STATUS["NOT_AUTHORIZED"] = "not_authorized";
    // 402
    ERROR_STATUS["DOES_NOT_EXIST"] = "does_not_exist_error";
    ERROR_STATUS["INVALID_CONFIG"] = "invalid_config";
    ERROR_STATUS["INVALID_STATE"] = "invalid_state";
    // --- 500
    ERROR_STATUS["UNKNOWN"] = "unknown";
    // storage layer errors
    ERROR_STATUS["CONTENT_NOT_FOUND"] = "content_not_found";
    ERROR_STATUS["WRITE_FAILED"] = "write_failed";
    ERROR_STATUS["DELETE_FAILED"] = "delete_failed";
    ERROR_STATUS["RENAME_FAILED"] = "rename_failed";
})(ERROR_STATUS || (ERROR_STATUS = {}));
export var USER_MESSAGES;
(function (USER_MESSAGES) {
    USER_MESSAGES["UNKNOWN"] = "unknown";
})(USER_MESSAGES || (USER_MESSAGES = {}));
/**
 * Labels whether error is recoverable or not
 */
export var ERROR_SEVERITY;
(function (ERROR_SEVERITY) {
    ERROR_SEVERITY["MINOR"] = "minor";
    ERROR_SEVERITY["FATAL"] = "fatal";
})(ERROR_SEVERITY || (ERROR_SEVERITY = {}));
export var RESERVED_KEYS;
(function (RESERVED_KEYS) {
    RESERVED_KEYS["GIT_NOTE_PATH"] = "gitNotePath";
    RESERVED_KEYS["GIT_NO_LINK"] = "gitNoLink";
})(RESERVED_KEYS || (RESERVED_KEYS = {}));
export const TAGS_HIERARCHY_BASE = "tags";
/** Notes under this hierarchy are considered tags, for example `${TAGS_HIERARCHY}foo` is a tag note. */
export const TAGS_HIERARCHY = `${TAGS_HIERARCHY_BASE}.`;
export const TAGS_PREFIX = "#";
export const TAGS_POSTFIX = "";
export const ZDOCS_HIERARCHY_BASE = "source.zdoc";
export const ZDOCS_HIERARCHY = `${ZDOCS_HIERARCHY_BASE}.`;
export const ZDOCS_TAG_PREFIX = "\\cite{";
export const ZDOCS_TAG_PREFIX_REGEX = "\\\\cite\\{";
export const ZDOCS_TAG_SUFFIX = "}";
export const ZDOCS_TAG_SUFFIX_REGEX = "\\}";
export const SPECIAL_TAGS = [
    {
        "base": "source.zdoc",
        "prefix": "\\cite{",
        "postfix": "}"
    }
];
export var SAIL_EMOJIS;
(function (SAIL_EMOJIS) {
    SAIL_EMOJIS["SEEDLING"] = "\uD83C\uDF31";
    SAIL_EMOJIS["OKAY"] = "\u2705";
    SAIL_EMOJIS["NOT_OKAY"] = "\u274E";
})(SAIL_EMOJIS || (SAIL_EMOJIS = {}));
export var SAIL_VSCODE_CONFIG_KEYS;
(function (SAIL_VSCODE_CONFIG_KEYS) {
    SAIL_VSCODE_CONFIG_KEYS["ENABLE_SELF_CONTAINED_VAULTS_WORKSPACE"] = "sail.enableSelfContainedVaultWorkspace";
})(SAIL_VSCODE_CONFIG_KEYS || (SAIL_VSCODE_CONFIG_KEYS = {}));
/**
 * Keys to a global state store. Global here means across a single user's
 * different access platforms.
 */
export var GLOBAL_STATE_KEYS;
(function (GLOBAL_STATE_KEYS) {
    GLOBAL_STATE_KEYS["ANONYMOUS_ID"] = "telemetry.anonymousId";
})(GLOBAL_STATE_KEYS || (GLOBAL_STATE_KEYS = {}));
//# sourceMappingURL=index.js.map