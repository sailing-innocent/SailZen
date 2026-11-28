import { DeleteSchemaResp, SailConfig, DEngine, DEngineClient, DEngineInitResp, DHookDict, EngineInitOpts, EngineState, DVault, EngineDeleteOpts, EngineInfoResp, EngineSchemaWriteOpts, EngineBase, EngineWriteOptsV2, GetDecorationsOpts, GetDecorationsResp, GetNoteBlocksOpts, GetNoteBlocksResp, GetSchemaResp, IFileStore, INoteStore, IQueryStore, ISchemaStore, NoteProps, QuerySchemaResp, RenameNoteOpts, RenameNoteResp, RenderNoteOpts, RenderNoteResp, SchemaModuleProps, WorkspaceOpts, WriteNoteResp, WriteSchemaResp } from "@saili/common-all";
import { DLogger } from "@saili/common-server";
type SailEngineOptsV3 = {
    wsRoot: string;
    vaults: DVault[];
    fileStore: IFileStore;
    noteStore: INoteStore<string>;
    queryStore: IQueryStore;
    schemaStore: ISchemaStore<string>;
    logger: DLogger;
    config: SailConfig;
};
export declare class SailEngine extends EngineBase implements DEngine {
    wsRoot: string;
    hooks: DHookDict;
    private _fileStore;
    private _noteStore;
    private _schemaStore;
    private _renderedCache;
    /**
     * Current lifecycle state of the engine. In-memory only, never persisted.
     * - cold: not initialized
     * - warm: minimal init finished (schemas + priority notes parsed, stubs
     *   registered). The daily journal path is usable.
     * - ready: full index finished.
     */
    private _state;
    /**
     * Ids of stub notes registered by {@link SailEngine.initMinimal}. Tracked so
     * that the full init can remove stubs that were never promoted to full
     * notes or overwritten by writes.
     */
    private _stubNoteIds;
    /**
     * Per-vault progress of a running full index, exposed for status polling.
     */
    private _initProgress?;
    constructor(props: SailEngineOptsV3);
    /** Current engine lifecycle state. */
    getEngineState(): EngineState;
    /** Per-vault progress of the full index, when one is running. */
    getInitProgress(): {
        vaultsDone: number;
        vaultsTotal: number;
    } | undefined;
    static create({ wsRoot, logger }: {
        logger?: DLogger;
        wsRoot: string;
    }): SailEngine;
    /**
     * Does not throw error but returns it
     *
     * @param opts when `opts.mode === "minimal"`, only schemas plus the given
     * priority paths are parsed and stubs are registered for all other notes,
     * returning as soon as the daily journal path is usable. Defaults to a full
     * index.
     */
    init(opts?: EngineInitOpts): Promise<DEngineInitResp>;
    /**
     * Minimal engine initialization (fast-first startup).
     *
     * Fully parses all schemas plus the notes matching `priorityPaths`
     * (fnames or fpaths without the `.md` extension, e.g. today's journal note
     * and the journal template) and registers lightweight stub entries
     * (fname -> id mapping only, no body parsing) for every other note on
     * disk. This makes the following usable without waiting for a full index:
     * - schema queries (`doesSchemaExist`)
     * - single note lookups by fname (`findNotesMeta`)
     * - `writeNote` dedup and ancestor resolution (daily journal creation)
     *
     * Stubs never enter the fuse index; backlinks and the full index are only
     * built once {@link SailEngine.init} runs to completion (ready state).
     *
     * Does not throw but returns errors, same as {@link SailEngine.init}.
     */
    initMinimal({ priorityPaths, }?: {
        priorityPaths?: string[];
    }): Promise<DEngineInitResp>;
    /**
     * See {@link DEngine.writeNote}
     */
    writeNote(note: NoteProps, opts?: EngineWriteOptsV2): Promise<WriteNoteResp>;
    /**
     * See {@link DEngine.renameNote}
     *
     * TODO: make atomic
     */
    renameNote(opts: RenameNoteOpts): Promise<RenameNoteResp>;
    /**
     * See {@link DEngine.getSchema}
     */
    getSchema(id: string): Promise<GetSchemaResp>;
    /**
     * See {@link DEngine.writeSchema}
     */
    writeSchema(schema: SchemaModuleProps, opts?: EngineSchemaWriteOpts): Promise<WriteSchemaResp>;
    /**
     * See {@link DEngine.deleteSchema}
     */
    deleteSchema(id: string, opts?: EngineDeleteOpts): Promise<DeleteSchemaResp>;
    info(): Promise<EngineInfoResp>;
    /**
     * See {@link DEngine.querySchema}
     */
    querySchema(queryString: string): Promise<QuerySchemaResp>;
    renderNote({ id, note, flavor, dest, }: RenderNoteOpts): Promise<RenderNoteResp>;
    getNoteBlocks(opts: GetNoteBlocksOpts): Promise<GetNoteBlocksResp>;
    getDecorations(opts: GetDecorationsOpts): Promise<GetDecorationsResp>;
    private initSchema;
    /**
     * Construct dictionary of NoteProps from workspace on filesystem
     *
     * For every vault on the filesystem, get list of files and convert each file to NoteProp
     * @returns NotePropsByIdDict
     */
    private initNotes;
    private createRenderedCache;
    /**
     * Create and add backlinks from all notes with a link pointing to another note
     */
    private addBacklinks;
    /**
     * Recursively search through fname to find next available ancestor note.
     *
     * E.g, if fpath = "baz.foo.bar", search for "baz.foo", then "baz", then "root" until first valid note is found
     * @param fpath of note to find ancestor of
     * @param vault of ancestor note
     * @returns closest ancestor note
     */
    private findClosestAncestor;
    /**
     * Update the links inside this note that need to be updated for the rename
     * from `oldLoc` to `newLoc` Will update the note in place and return note if
     * something has changed
     */
    private processNoteChangedByRename;
    private referenceRangeParts;
    private isCachedPreviewUpToDate;
    /**
     * Check if there exists a note reference that is newer than the provided "latestUpdated"
     * This is used to determine if a cached preview is up-to-date
     *
     * Preview note tree includes links whose content is rendered in the rootNote preview,
     * particularly the reference links (![[ref-link-example]]).
     */
    private _isCachedPreviewUpToDate;
    private _renderNote;
    private updateNotesWithLinkCandidates;
}
export declare const createEngineV3: ({ wsRoot }: WorkspaceOpts) => DEngineClient;
export {};
