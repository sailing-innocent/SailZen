import { DEngineClient, DVault, ISailError, NoteDicts, SchemaModuleDict } from "@saili/common-all";
import { DLogger } from "@saili/common-server";
import { NotesFileSystemCache } from "../../cache/notesFileSystemCache";
export type FileMeta = {
    fpath: string;
};
export type FileMetaDict = {
    [key: string]: FileMeta[];
};
export declare class NoteParserV2 {
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
     * @returns
     */
    parseFiles(allPaths: string[], vault: DVault, schemas: SchemaModuleDict): Promise<{
        noteDicts: NoteDicts;
        errors: ISailError[];
    }>;
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
