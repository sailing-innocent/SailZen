import fs, { Dirent } from "fs-extra";
import { FSWatcher } from "fs";
import matter from "gray-matter";
import YAML from "js-yaml";
import _ from "lodash";
import os from "os";
import path from "path";
import anymatch from "anymatch";
import { assign, CommentJSONValue, parse, stringify } from "comment-json";
// @ts-ignore
import tmp, { DirResult, dirSync } from "tmp";
import {
  cleanName,
  CONSTANTS,
  DVault,
  ERROR_SEVERITY,
  ERROR_STATUS,
  FOLDERS,
  genHash,
  GetAllFilesOpts,
  globMatch,
  isNotNull,
  isNotUndefined,
  NoteProps,
  NoteUtils,
  RespV2,
  RespV3,
  AnyJson,
  fromPromise,
  fromThrowable,
  Result,
  SailError,
  SchemaModuleOpts,
  SchemaModuleProps,
  SchemaUtils,
  string2Note,
  VaultUtils,
} from "@saili/common-all";


/**
 *
 * Normalize file name
 * - strip off extension
 * - replace [.\s] with -
 * @param name
 * @param opts
 *   - isDir: dealing with directory
 */
export function cleanFileName(
  name: string,
  opts?: { isDir?: boolean }
): string {
  const cleanOpts = _.defaults(opts, { isDir: false });
  if (!cleanOpts.isDir) {
    const { name: fname, dir } = path.parse(name);
    // strip off extension
    name = path.join(dir, fname);
  }
  name = name.replace(/\./g, "-");
  // replace all names already in file name
  //name = name.replace(/\./g, "-");
  name = cleanName(name);
  // if file, only get name (no extension)
  return name;
}

export function findInParent(
  base: string,
  fname: string
): string | undefined {
  return findUpTo({ base, fname, maxLvl: 10, returnDirPath: true });
}

export function readMD(fpath: string): { data: any; content: string } {
  return matter.read(fpath, {});
}

/**
 *
 * @param fpath path of yaml file to read
 * @param overwriteDuplcate if set to true, will not throw duplicate entry exception and use the last entry.
 * @returns
 */
export function readYAML(fpath: string, overwriteDuplicate?: boolean): any {
  return YAML.load(fs.readFileSync(fpath, { encoding: "utf8" }), {
    schema: YAML.JSON_SCHEMA,
    json: overwriteDuplicate ?? false,
  });
}

export async function readYAMLAsync(fpath: string): Promise<any> {
  return YAML.load(await fs.readFile(fpath, { encoding: "utf8" }), {
    schema: YAML.JSON_SCHEMA,
  });
}

export function writeYAML(fpath: string, data: any) {
  const out = YAML.dump(data, { indent: 4, schema: YAML.JSON_SCHEMA });
  return fs.writeFileSync(fpath, out);
}

export function writeYAMLAsync(fpath: string, data: any) {
  const out = YAML.dump(data, { indent: 4, schema: YAML.JSON_SCHEMA });
  return fs.writeFile(fpath, out);
}

export function deleteFile(fpath: string) {
  return fs.unlinkSync(fpath);
}

/** Gets all files in `root`, with include and exclude lists (glob matched)
 *
 * This function returns the full `Dirent` which gives you access to file
 * metadata. If you don't need the metadata, see {@link getAllFiles}.
 *
 * @throws a `SailError` with `ERROR_SEVERITY.MINOR`. This is to avoid
 * crashing the Sail initialization, please catch the error and modify the
 * severity if needed.
 */
export async function getAllFilesWithTypes(
  opts: GetAllFilesOpts
): Promise<RespV2<Dirent[]>> {
  const { root } = _.defaults(opts, {
    exclude: [".git", "Icon\r", ".*"],
  });
  try {
    const allFiles = await fs.readdir(root.fsPath, { withFileTypes: true });
    return {
      data: allFiles
        .map((dirent) => {
          const { name: fname } = dirent;
          // match exclusions
          if (
            _.some([dirent.isDirectory(), globMatch(opts.exclude || [], fname)])
          ) {
            return null;
          }
          // match inclusion
          if (opts.include && !globMatch(opts.include, fname)) {
            return null;
          }
          return dirent;
        })
        .filter(isNotNull),
      error: null,
    };
  } catch (err) {
    return {
      error: new SailError({
        message: "Error when reading the vault",
        payload: err,
        // Marked as minor to avoid stopping initialization. Even if we can't read one vault, we might be able to read other vaults.
        severity: ERROR_SEVERITY.MINOR,
      }),
    };
  }
}

/** Gets all files in `root`, with include and exclude lists (glob matched)
 *
 * This function returns only the file name. If you need the file metadata, see
 * {@link getAllFilesWithTypes}.
 *
 * @throws a `SailError` with `ERROR_SEVERITY.MINOR`. This is to avoid
 * crashing the Sail initialization, please catch the error and modify the
 * severity if needed.
 */
export async function getAllFiles(
  opts: GetAllFilesOpts
): Promise<RespV2<string[]>> {
  const out = await getAllFilesWithTypes(opts);
  const data = out.data?.map((item) => item.name);
  return { error: out.error, data };
}

/**
 * Convert a node to a MD File. Any custom attributes will be
 * added to the end
 *
 * @param node: node to convert
 * @param opts
 *   - root: root folder where files should be written to
 */
export function resolveTilde(filePath: string) {
  if (!filePath || typeof filePath !== "string") {
    return "";
  }
  // '~/folder/path' or '~'
  if (
    filePath[0] === "~" &&
    (filePath[1] === path.sep || filePath.length === 1)
  ) {
    return filePath.replace("~", os.homedir());
  }
  return filePath;
}

/**
 * Resolve file path and resolve relative paths relative to `root`
 * @param filePath
 * @param root
 */
export function resolvePath(filePath: string, root?: string): string {
  const platform = os.platform();
  const isWin = platform === "win32";
  if (filePath[0] === "~") {
    return resolveTilde(filePath);
  } else if (
    path.isAbsolute(filePath) ||
    (isWin && filePath.startsWith("\\"))
  ) {
    return filePath;
  } else {
    if (!root) {
      throw Error("can't use rel path without a workspace root set");
    }
    return path.join(root, filePath);
  }
}

// @deprecate, NoteUtils.normalizeFname
export function removeMDExtension(nodePath: string) {
  const idx = nodePath.lastIndexOf(".md");
  if (idx > 0) {
    nodePath = nodePath.slice(0, idx);
  }
  return nodePath;
}

const readFileSync = fromThrowable(fs.readFileSync, (error) => {
  return new SailError({
    message: `Cannot find ${path}`,
    severity: ERROR_SEVERITY.FATAL,
    ...(error instanceof Error && { innerError: error }),
  });
});

export function readString(path: string) {
  return readFileSync(path, "utf8") as Result<string, SailError>;
}

export function readJson(path: string) {
  return fromPromise<AnyJson, SailError>(fs.readJSON(path), (error) => {
    return new SailError({
      message: `Cannot find ${path}`,
      severity: ERROR_SEVERITY.FATAL,
      ...(error instanceof Error && { innerError: error }),
    });
  });
}



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
export const COMMON_FOLDER_IGNORES: string[] = [
  "**/.*/**", // Any folder starting with .
  "**/node_modules/**", // nodejs
  "**/.git/**", // git
  "**/__pycache__/**", // python
];

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

export async function createFileWatcher(
  opts: CreateFileWatcherOpts
): Promise<CreateFileWatcherResp> {
  const { numTries, fpath, onChange } = _.defaults(opts, {
    numTries: 5,
  });
  const didCreate = false;

  return new Promise((resolve, _reject) => {
    if (!fs.existsSync(fpath)) {
      return setTimeout(() => {
        resolve(
          _createFileWatcher({
            ...opts,
            numTries: numTries - 1,
            isCreate: true,
          })
        );
      }, 3000);
    }
    const watcher = fs.watch(fpath, () => {
      onChange({ fpath });
    });
    return resolve({ watcher, didCreate });
  });
}

async function _createFileWatcher(
  opts: CreateFileWatcherOpts & { isCreate: boolean }
): Promise<CreateFileWatcherResp> {
  const { numTries, fpath, onChange, onCreate } = _.defaults(opts, {
    numTries: 5,
  });
  if (numTries <= 0) {
    throw new SailError({ message: "exceeded numTries" });
  }
  return new Promise(async (resolve, _reject) => {
    if (!fs.existsSync(fpath)) {
      console.log({ fpath, msg: "not exist" });
      return setTimeout(() => {
        resolve(createFileWatcher({ ...opts, numTries: numTries - 1 }));
      }, 3000);
    }
    await onCreate({ fpath });
    const watcher = fs.watch(fpath, () => {
      onChange({ fpath });
    });
    return resolve({ watcher, didCreate: true });
  });
}



// TODO: consider throwing error if no frontmatter
export function file2Note(
  fpath: string,
  vault: DVault,
  toLowercase?: boolean
): RespV3<NoteProps> {
  if (!fs.existsSync(fpath)) {
    const error = SailError.createFromStatus({
      status: ERROR_STATUS.INVALID_STATE,
      message: `${fpath} does not exist`,
    });
    return {
      error,
    };
  } else {
    const content = fs.readFileSync(fpath, { encoding: "utf8" });
    const { name } = path.parse(fpath);
    const fname = toLowercase ? name.toLowerCase() : name;
    return {
      data: string2Note({ content, fname, vault }),
    };
  }
}

/** Read the contents of a note from the filesystem.
 *
 * Warning! The note contents may be out of date compared to changes in the editor.
 * Consider using `NoteUtils.serialize` instead.
 */
export function note2String(opts: {
  note: NoteProps;
  wsRoot: string;
}): Promise<string> {
  const notePath = NoteUtils.getFullPath(opts);
  return fs.readFile(notePath, { encoding: "utf8" });
}

/**
 * Go to dirname that {fname} is contained in
 * @param maxLvl? - default: 10
 @deprecated use {@link findUpTo}
 */
export function goUpTo(opts: {
  base: string;
  fname: string;
  maxLvl?: number;
}): string {
  const { base, fname, maxLvl } = opts;
  const found = findUpTo({ base, fname, maxLvl, returnDirPath: true });
  if (!found) {
    throw Error(`no root found from ${base}`);
  }
  return found;
}

/**
 * Go to dirname that {fname} is contained in, going out (up the tree) from base.
 * @param maxLvl - default: 3
 * @param returnDirPath - return path to directory, default: false
 */
export function findUpTo(opts: {
  base: string;
  fname: string;
  maxLvl?: number;
  returnDirPath?: boolean;
}): string | undefined {
  const { fname, base, maxLvl, returnDirPath } = _.defaults(opts, {
    maxLvl: 3,
    returnDirPath: false,
  });
  const lvls = [];
  let acc = 0;
  while (maxLvl - acc > 0) {
    const tryPath = path.join(base, ...lvls, fname);
    if (fs.existsSync(tryPath)) {
      return returnDirPath ? path.dirname(tryPath) : tryPath;
    }
    acc += 1;
    lvls.push("..");
  }
  return undefined;
}

export const WS_FILE_MAX_SEARCH_DEPTH = 3;

/**
 * Go to dirname that {fname} is contained in, going in (deeper into tree) from base.
 * @param maxLvl Default 3, how deep to go down in the file tree. Keep in mind that the tree gets wider and this search becomes exponentially more expensive the deeper we go.
 * @param returnDirPath - return path to directory, default: false
 *
 * One warning: this will not search into folders starting with `.` to avoid searching through things like the `.git` folder.
 */
export async function findDownTo(opts: {
  base: string;
  fname: string;
  maxLvl?: number;
  returnDirPath?: boolean;
}): Promise<string | undefined> {
  const { fname, base, maxLvl, returnDirPath } = {
    maxLvl: WS_FILE_MAX_SEARCH_DEPTH,
    returnDirPath: false,
    ...opts,
  };
  const contents = await fs.readdir(base);
  let found = contents.filter((foundFile) => foundFile === fname)[0];
  if (found) {
    found = path.join(base, found);
    return returnDirPath ? path.dirname(found) : found;
  }
  if (maxLvl > 1) {
    // Keep searching recursively
    return (
      await Promise.all(
        contents.map(async (folder) => {
          // Find the folders in the current folder
          const subfolder = await fs.stat(path.join(base, folder));
          if (!subfolder.isDirectory()) return;
          // Exclude folders starting with . to skip stuff like `.git`
          if (anymatch(COMMON_FOLDER_IGNORES, folder)) return;
          return findDownTo({
            ...opts,
            base: path.join(base, folder),
            maxLvl: maxLvl - 1,
          });
        })
      )
    ).filter(isNotUndefined)[0];
  }
  return undefined;
}

/** Returns true if `inner` is inside of `outer`, and false otherwise.
 *
 * If `inner === outer`, then that also returns false.
 */
export function isInsidePath(outer: string, inner: string) {
  // When going from `outer` to `inner`
  const relPath = path.relative(outer, inner);
  // If we have to leave `outer`, or if we have to switch to a
  // different drive with an absolute path, then `inner` can't be
  // inside `outer` (or `inner` and `outer` are identical)
  return (
    !relPath.startsWith("..") && !path.isAbsolute(relPath) && relPath !== ""
  );
}

/** Returns the list of unique, outermost folders. No two folders returned are nested within each other. */
export function uniqueOutermostFolders(folders: string[]) {
  // Avoid duplicates
  folders = _.uniq(folders);
  if (folders.length === 1) return folders;
  return folders.filter((currentFolder) =>
    folders.every((otherFolder) => {
      // `currentFolder` is not inside any other folder
      return !isInsidePath(otherFolder, currentFolder);
    })
  );
}

/**
 * Return hash of written file
 */
export async function note2File({
  note,
  vault,
  wsRoot,
}: {
  note: NoteProps;
  vault: DVault;
  wsRoot: string;
}) {
  const { fname } = note;
  const ext = ".md";
  const payload = NoteUtils.serialize(note, { excludeStub: true });
  const vpath = vault2Path({ vault, wsRoot });
  await fs.writeFile(path.join(vpath, fname + ext), payload);
  return genHash(payload);
}

function serializeModuleOpts(moduleOpts: SchemaModuleOpts) {
  const { version, imports, schemas } = _.defaults(moduleOpts, {
    imports: [],
  });
  const out = {
    version,
    imports,
    schemas: _.values(schemas).map((ent) =>
      SchemaUtils.serializeSchemaProps(ent)
    ),
  };
  return YAML.dump(out, { schema: YAML.JSON_SCHEMA });
}

export function schemaModuleOpts2File(
  schemaFile: SchemaModuleOpts,
  vaultPath: string,
  fname: string
) {
  const ext = ".schema.yml";
  return fs.writeFile(
    path.join(vaultPath, fname + ext),
    serializeModuleOpts(schemaFile)
  );
}

export function schemaModuleProps2File(
  schemaMProps: SchemaModuleProps,
  vpath: string,
  fname: string
) {
  const ext = ".schema.yml";
  return fs.writeFile(
    path.join(vpath, fname + ext),
    SchemaUtils.serializeModuleProps(schemaMProps)
  );
}

export function assignJSONWithComment(jsonObj: any, dataToAdd: any) {
  return assign(
    {
      ...dataToAdd,
    },
    jsonObj
  );
}

export async function readJSONWithComments(
  fpath: string
): Promise<CommentJSONValue | null> {
  const content = await fs.readFile(fpath);
  const obj = parse(content.toString());
  return obj;
}

export function readJSONWithCommentsSync(fpath: string): CommentJSONValue {
  const content = fs.readFileSync(fpath);
  const obj = parse(content.toString());
  return obj;
}

export function tmpDir(): DirResult {
  const dirPath = dirSync();
  return dirPath;
}

/** Returns the path to where the notes are stored inside the vault.
 *
 * For self contained vaults, this is the `notes` folder inside of the vault.
 * For other vault types, this is the root of the vault itself.
 *
 * If you always need the root of the vault, use {@link pathForVaultRoot} instead.
 */
export const vault2Path = ({
  vault,
  wsRoot,
}: {
  vault: DVault;
  wsRoot: string;
}) => {
  return resolvePath(VaultUtils.getRelPath(vault), wsRoot);
};

/** Returns the root of the vault.
 *
 * This is similar to {@link vault2Path}, the only difference is that for self
 * contained vaults `vault2Path` returns the `notes` folder inside the vault,
 * while this returns the root of the vault.
 */
export function pathForVaultRoot({
  vault,
  wsRoot,
}: {
  vault: DVault;
  wsRoot: string;
}) {
  if (VaultUtils.isSelfContained(vault))
    return resolvePath(path.join(wsRoot, vault.fsPath));
  return vault2Path({ vault, wsRoot });
}

export function writeJSONWithCommentsSync(fpath: string, data: any) {
  const payload = stringify(data, null, 4);
  return fs.writeFileSync(fpath, payload);
}

export async function writeJSONWithComments(fpath: string, data: any) {
  const payload = stringify(data, null, 4);
  return fs.writeFile(fpath, payload);
}

/**
 * Turn . delimited file to / separated
 */
export function dot2Slash(fname: string) {
  return fname.replace(/\./g, "/");
}

/** Checks that the `path` contains a file. */
export async function fileExists(path: string) {
  try {
    const stat = await fs.stat(path);
    return stat.isFile();
  } catch {
    return false;
  }
}

/** Finds if a file `fpath` is located in any vault.
 *
 * @param fpath A file name or relative path that we are searching inside vaults.
 */
async function findFileInVault({
  fpath,
  wsRoot,
  vaults,
}: {
  fpath: string;
  wsRoot: string;
  vaults: DVault[];
}): Promise<{ vault: DVault; fullPath: string } | undefined> {
  // Assets from later vaults will overwrite earlier ones.
  vaults = [...vaults].reverse();
  for (const vault of vaults) {
    const fullPath = path.join(wsRoot, VaultUtils.getRelPath(vault), fpath);
    // Doing this sequentially to simulate how publishing handles conflicting assets.
    // eslint-disable-next-line no-await-in-loop
    if (await fileExists(fullPath)) {
      return { vault, fullPath };
    }
  }
  return;
}

export async function findNonNoteFile(opts: {
  fpath: string;
  wsRoot: string;
  vaults: DVault[];
  currentVault?: DVault;
}): Promise<{ vault?: DVault; fullPath: string } | undefined> {
  let { fpath } = opts;
  if (path.isAbsolute(fpath)) {
    // The path could be an absolute path. If it is and the file exists, then directly use that.
    if (await fileExists(fpath)) return { fullPath: fpath };
  }
  // Not an absolute path. Then the leading slash is meaningless:
  // `/assets` and `assets` refers to the same place.
  fpath = _.trim(fpath, "/\\");
  // Check if this is an asset first
  if (fpath.startsWith("assets")) {
    const out = await findFileInVault(opts);
    if (out !== undefined) return out;
  }
  // If not an asset, this also might be relative to the current note
  if (opts.currentVault) {
    const fullPath = path.join(
      opts.wsRoot,
      VaultUtils.getRelPath(opts.currentVault),
      fpath
    );
    if (await fileExists(fullPath))
      return { fullPath, vault: opts.currentVault };
  }
  // If not an asset, or if we couldn't find it in assets, then check from wsRoot for out-of-vault files
  const fullPath = path.join(opts.wsRoot, fpath);
  if (await fileExists(fullPath)) return { fullPath };
  // Otherwise, it just doesn't exist
  return undefined;
}

class FileUtils {
  /**
   * Keep incrementing a numerical suffix until we find a path name that does not correspond to an existing file
   * @param param0
   */
  static genFilePathWithSuffixThatDoesNotExist({
    fpath,
    sep = "-",
  }: {
    fpath: string;
    sep?: string;
  }) {
    // Try to put into `fpath`. If `fpath` exists, create a new folder with an numbered suffix
    let acc = 0;
    let tryPath = fpath;
    while (fs.pathExistsSync(tryPath)) {
      acc += 1;
      tryPath = [fpath, acc].join(sep);
    }
    return { filePath: tryPath, acc };
  }
  /**
   * Check if a file starts with a prefix string
   * @param fpath: full path to the file
   * @param prefix: string prefix to check for
   */
  static matchFilePrefix = async ({
    fpath,
    prefix,
  }: {
    fpath: string;
    prefix: string;
  }): Promise<RespV3<boolean>> => {
    // solution adapted from https://stackoverflow.com/questions/70707646/reading-part-of-file-in-node
    return new Promise((resolve) => {
      const fileStream = fs.createReadStream(fpath, { highWaterMark: 60 });
      const prefixLength = prefix.length;
      fileStream
        .on("error", (err) =>
          resolve({
            error: new SailError({ innerError: err, message: "error" }),
          })
        )
        // we got to the end without a match
        .on("end", () => resolve({ data: false }))
        .on("data", (chunk: any) => {
          // eslint-disable-next-line no-plusplus
          for (let i = 0; i < chunk.length; i++) {
            const a = String.fromCharCode(chunk[i]);
            // not a match, return
            if (a !== prefix[i]) {
              resolve({ data: false });
            }
            // all matches
            if (i === prefixLength - 1) {
              resolve({ data: true });
            }
          }
        });
    });
  };
}

/** Looks at the files at the given path to check if it's a self contained vault. */
export async function isSelfContainedVaultFolder(dir: string) {
  return _.every(
    await Promise.all([
      fs.pathExists(path.join(dir, CONSTANTS.SAIL_CONFIG_FILE)),
      fs.pathExists(path.join(dir, FOLDERS.NOTES)),
    ])
  );
}

/** Move a file or folder from `from` to `to`, if the file exists.
 *
 * @returns True if the file did exist and was moved successfully, false otherwise.
 */
export async function moveIfExists(from: string, to: string): Promise<boolean> {
  try {
    if (await fs.pathExists(from)) {
      await fs.move(from, to);
      return true;
    }
  } catch (err) {
    // Permissions error or similar issue when moving the path
    // deliberately left empty
  }
  return false;
}

/** Utility functions for dealing with file extensions. */
export class FileExtensionUtils {
  private static textExtensions: ReadonlySet<string>;
  private static ensureTextExtensions() {
    if (this.textExtensions === undefined) {
      this.textExtensions = new Set(
        ["md", "txt"]
      );
    }
  }

  /** Checks if a given file extension is a well known text file extension. */
  static isTextFileExtension(extension: string) {
    extension = _.trimStart(extension, ".").toLowerCase();
    this.ensureTextExtensions();
    return this.textExtensions.has(extension);
  }
}

export { tmp, DirResult, FileUtils };
