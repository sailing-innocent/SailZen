import { DeleteSchemaResp, SailConfig, DEngine, DEngineClient, DEngineInitResp, DHookDict, DVault, EngineDeleteOpts, EngineInfoResp, EngineSchemaWriteOpts, EngineV3Base, EngineWriteOptsV2, GetDecorationsOpts, GetDecorationsResp, GetNoteBlocksOpts, GetNoteBlocksResp, GetSchemaResp, IFileStore, INoteStore, IQueryStore, ISchemaStore, NoteProps, QuerySchemaResp, RenameNoteOpts, RenameNoteResp, RenderNoteOpts, RenderNoteResp, SchemaModuleProps, WorkspaceOpts, WriteNoteResp, WriteSchemaResp } from "@saili/common-all";
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
export declare class SailEngineV3 extends EngineV3Base implements DEngine {
    wsRoot: string;
    hooks: DHookDict;
    private _fileStore;
    private _noteStore;
    private _schemaStore;
    private _renderedCache;
    constructor(props: SailEngineOptsV3);
    static create({ wsRoot, logger }: {
        logger?: DLogger;
        wsRoot: string;
    }): SailEngineV3;
    /**
     * Does not throw error but returns it
     */
    init(): Promise<DEngineInitResp>;
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
