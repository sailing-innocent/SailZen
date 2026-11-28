import { Dirent } from "fs-extra";
import { FSWatcher } from "fs";
import { CommentJSONValue } from "comment-json";
import tmp, { DirResult } from "tmp";
import { DVault, GetAllFilesOpts, NoteProps, RespV2, RespV3, AnyJson, Result, SailError, SchemaModuleOpts, SchemaModuleProps } from "@saili/common-all";
/**
 *
 * Normalize file name
 * - strip off extension
 * - replace [.\s] with -
 * @param name
 * @param opts
 *   - isDir: dealing with directory
 */
export declare function cleanFileName(name: string, opts?: {
    isDir?: boolean;
}): string;
export declare function findInParent(base: string, fname: string): string | undefined;
export declare function readMD(fpath: string): {
    data: any;
    content: string;
};
/**
 *
 * @param fpath path of yaml file to read
 * @param overwriteDuplcate if set to true, will not throw duplicate entry exception and use the last entry.
 * @returns
 */
export declare function readYAML(fpath: string, overwriteDuplicate?: boolean): any;
export declare function readYAMLAsync(fpath: string): Promise<any>;
export declare function writeYAML(fpath: string, data: any): void;
export declare function writeYAMLAsync(fpath: string, data: any): Promise<void>;
export declare function deleteFile(fpath: string): void;
/** Gets all files in `root`, with include and exclude lists (glob matched)
 *
 * This function returns the full `Dirent` which gives you access to file
 * metadata. If you don't need the metadata, see {@link getAllFiles}.
 *
 * @throws a `SailError` with `ERROR_SEVERITY.MINOR`. This is to avoid
 * crashing the Sail initialization, please catch the error and modify the
 * severity if needed.
 */
export declare function getAllFilesWithTypes(opts: GetAllFilesOpts): Promise<RespV2<Dirent[]>>;
/** Gets all files in `root`, with include and exclude lists (glob matched)
 *
 * This function returns only the file name. If you need the file metadata, see
 * {@link getAllFilesWithTypes}.
 *
 * @throws a `SailError` with `ERROR_SEVERITY.MINOR`. This is to avoid
 * crashing the Sail initialization, please catch the error and modify the
 * severity if needed.
 */
export declare function getAllFiles(opts: GetAllFilesOpts): Promise<RespV2<string[]>>;
/**
 * Convert a node to a MD File. Any custom attributes will be
 * added to the end
 *
 * @param node: node to convert
 * @param opts
 *   - root: root folder where files should be written to
 */
export declare function resolveTilde(filePath: string): string;
/**
 * Resolve file path and resolve relative paths relative to `root`
 * @param filePath
 * @param root
 */
export declare function resolvePath(filePath: string, root?: string): string;
export declare function removeMDExtension(nodePath: string): string;
export declare function readString(path: string): Result<string, SailError>;
export declare function readJson(path: string): import("@saili/common-all").ResultAsync<AnyJson, SailError<import("@saili/common-all").StatusCodes | undefined>>;
/** Sail should ignore any of these folders when watching or searching folders.
 *
 * These folders are unlikely to contain anything Sail would like to find, so we can ignore them.
 *
 * Example usage:
 * ```ts
 * if (!anymatch(COMMON_FOLDER_IGNORES, folder)) {
 *   // Good folder!
 * }
 * ```
 */
export declare const COMMON_FOLDER_IGNORES: string[];
type FileWatcherCb = {
    fpath: string;
};
type CreateFileWatcherOpts = {
    fpath: string;
    numTries?: number;
    onChange: (opts: FileWatcherCb) => Promise<any>;
    onCreate: (opts: FileWatcherCb) => Promise<any>;
};
type CreateFileWatcherResp = {
    watcher: FSWatcher;
    didCreate: boolean;
};
export declare function createFileWatcher(opts: CreateFileWatcherOpts): Promise<CreateFileWatcherResp>;
export declare function file2Note(fpath: string, vault: DVault, toLowercase?: boolean): RespV3<NoteProps>;
/** Read the contents of a note from the filesystem.
 *
 * Warning! The note contents may be out of date compared to changes in the editor.
 * Consider using `NoteUtils.serialize` instead.
 */
export declare function note2String(opts: {
    note: NoteProps;
    wsRoot: string;
}): Promise<string>;
/**
 * Go to dirname that {fname} is contained in
 * @param maxLvl? - default: 10
 @deprecated use {@link findUpTo}
 */
export declare function goUpTo(opts: {
    base: string;
    fname: string;
    maxLvl?: number;
}): string;
/**
 * Go to dirname that {fname} is contained in, going out (up the tree) from base.
 * @param maxLvl - default: 3
 * @param returnDirPath - return path to directory, default: false
 */
export declare function findUpTo(opts: {
    base: string;
    fname: string;
    maxLvl?: number;
    returnDirPath?: boolean;
}): string | undefined;
export declare const WS_FILE_MAX_SEARCH_DEPTH = 3;
/**
 * Go to dirname that {fname} is contained in, going in (deeper into tree) from base.
 * @param maxLvl Default 3, how deep to go down in the file tree. Keep in mind that the tree gets wider and this search becomes exponentially more expensive the deeper we go.
 * @param returnDirPath - return path to directory, default: false
 *
 * One warning: this will not search into folders starting with `.` to avoid searching through things like the `.git` folder.
 */
export declare function findDownTo(opts: {
    base: string;
    fname: string;
    maxLvl?: number;
    returnDirPath?: boolean;
}): Promise<string | undefined>;
/** Returns true if `inner` is inside of `outer`, and false otherwise.
 *
 * If `inner === outer`, then that also returns false.
 */
export declare function isInsidePath(outer: string, inner: string): boolean;
/** Returns the list of unique, outermost folders. No two folders returned are nested within each other. */
export declare function uniqueOutermostFolders(folders: string[]): string[];
/**
 * Return hash of written file
 */
export declare function note2File({ note, vault, wsRoot, }: {
    note: NoteProps;
    vault: DVault;
    wsRoot: string;
}): Promise<string>;
export declare function schemaModuleOpts2File(schemaFile: SchemaModuleOpts, vaultPath: string, fname: string): Promise<void>;
export declare function schemaModuleProps2File(schemaMProps: SchemaModuleProps, vpath: string, fname: string): Promise<void>;
export declare function assignJSONWithComment(jsonObj: any, dataToAdd: any): any;
export declare function readJSONWithComments(fpath: string): Promise<CommentJSONValue | null>;
export declare function readJSONWithCommentsSync(fpath: string): CommentJSONValue;
export declare function tmpDir(): DirResult;
/** Returns the path to where the notes are stored inside the vault.
 *
 * For self contained vaults, this is the `notes` folder inside of the vault.
 * For other vault types, this is the root of the vault itself.
 *
 * If you always need the root of the vault, use {@link pathForVaultRoot} instead.
 */
export declare const vault2Path: ({ vault, wsRoot, }: {
    vault: DVault;
    wsRoot: string;
}) => string;
/** Returns the root of the vault.
 *
 * This is similar to {@link vault2Path}, the only difference is that for self
 * contained vaults `vault2Path` returns the `notes` folder inside the vault,
 * while this returns the root of the vault.
 */
export declare function pathForVaultRoot({ vault, wsRoot, }: {
    vault: DVault;
    wsRoot: string;
}): string;
export declare function writeJSONWithCommentsSync(fpath: string, data: any): void;
export declare function writeJSONWithComments(fpath: string, data: any): Promise<void>;
/**
 * Turn . delimited file to / separated
 */
export declare function dot2Slash(fname: string): string;
/** Checks that the `path` contains a file. */
export declare function fileExists(path: string): Promise<boolean>;
export declare function findNonNoteFile(opts: {
    fpath: string;
    wsRoot: string;
    vaults: DVault[];
    currentVault?: DVault;
}): Promise<{
    vault?: DVault;
    fullPath: string;
} | undefined>;
declare class FileUtils {
    /**
     * Keep incrementing a numerical suffix until we find a path name that does not correspond to an existing file
     * @param param0
     */
    static genFilePathWithSuffixThatDoesNotExist({ fpath, sep, }: {
        fpath: string;
        sep?: string;
    }): {
        filePath: string;
        acc: number;
    };
    /**
     * Check if a file starts with a prefix string
     * @param fpath: full path to the file
     * @param prefix: string prefix to check for
     */
    static matchFilePrefix: ({ fpath, prefix, }: {
        fpath: string;
        prefix: string;
    }) => Promise<RespV3<boolean>>;
}
/** Looks at the files at the given path to check if it's a self contained vault. */
export declare function isSelfContainedVaultFolder(dir: string): Promise<boolean>;
/** Move a file or folder from `from` to `to`, if the file exists.
 *
 * @returns True if the file did exist and was moved successfully, false otherwise.
 */
export declare function moveIfExists(from: string, to: string): Promise<boolean>;
/** Utility functions for dealing with file extensions. */
export declare class FileExtensionUtils {
    private static textExtensions;
    private static ensureTextExtensions;
    /** Checks if a given file extension is a well known text file extension. */
    static isTextFileExtension(extension: string): boolean;
}
export { tmp, DirResult, FileUtils };
