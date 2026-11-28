import { DEngineClient, DVault, ISailError, NoteDicts, SchemaModuleDict } from "@saili/common-all";
import { DLogger } from "@saili/common-server";
import { NotesFileSystemCache } from "../../cache/notesFileSystemCache";
export type FileMeta = {
    fpath: string;
};
export type FileMetaDict = {
    [key: string]: FileMeta[];
};
export declare class NoteParser {
    opts: {
        cache: NotesFileSystemCache;
        engine: DEngineClient;
        logger: DLogger;
    };
    cache: NotesFileSystemCache;
    private engine;
    constructor(opts: {
        cache: NotesFileSystemCache;
        engine: DEngineClient;
        logger: DLogger;
    });
    get logger(): DLogger;
    /**
     * Construct in-memory
     *
     * @param allPaths
     * @param vault
     * @param schemas
     * @param opts `skipCacheCleanup`: when true, cache entries for files that
     * were not part of `allPaths` are kept (used by minimal init which parses a
     * subset of files). Cache entries for parsed files are still updated.
     * @returns
     */
    parseFiles(allPaths: string[], vault: DVault, schemas: SchemaModuleDict, opts?: {
        skipCacheCleanup?: boolean;
    }): Promise<{
        noteDicts: NoteDicts;
        errors: ISailError[];
    }>;
    /**
     * Create stub NoteProps (fname -> id mapping only, no body parsing, no file
     * reads) for the given file paths. Used during minimal engine init so that
     * fname lookups, write dedup and ancestor resolution work before the full
     * index runs.
     *
     * Notes are processed level by level so that parent entries exist before
     * their children. Files whose fname is already present in `noteDicts` (eg.
     * parsed priority notes) are skipped.
     *
     * @param allPaths note file paths relative to the vault root (with `.md`)
     * @param vault vault the files belong to
     * @param noteDicts existing dicts; stubs are added into them (mutated in place)
     */
    static parseStubs(allPaths: string[], vault: DVault, noteDicts: NoteDicts): {
        errors: ISailError[];
    };
    /**
     * Given a fpath, convert to NoteProp
     * Update parent/children metadata if parents = true
     *
     * @returns List of all notes changed. If a note has no direct parents, stub notes are added instead
     */
    private parseNoteProps;
    /**
     * Given a fpath, attempt to convert raw file contents into a NoteProp
     *
     * Look up metadata from cache. If contenthash hasn't changed, use metadata from cache.
     * Otherwise, reconstruct metadata from scratch
     *
     * @returns NoteProp associated with fpath
     */
    private file2NoteWithCache;
}
