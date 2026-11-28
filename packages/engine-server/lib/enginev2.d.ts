import { BulkWriteNotesOpts, DEngine, DEngineClient, DeleteSchemaResp, DEngineInitResp, DEngineMode, DHookDict, DNodeType, DStore, DVault, EngineSchemaWriteOpts, EngineDeleteOpts, EngineInfoResp, EngineWriteOptsV2, FindNoteOpts, FuseEngine, GetDecorationsOpts, GetDecorationsResp, GetNoteBlocksOpts, GetNoteBlocksResp, DendronConfig, NoteChangeEntry, NoteProps, NotePropsByIdDict, NotePropsMeta, QueryNotesResp, QueryNotesOpts, RenameNoteOpts, RenderNoteOpts, SchemaModuleProps, QuerySchemaResp, WorkspaceOpts, WriteNoteResp, BulkGetNoteResp, BulkGetNoteMetaResp, RenameNoteResp, RenderNoteResp, GetSchemaResp, GetNoteMetaResp, GetNoteResp } from "@saili/common-all";
import { DLogger } from "@saili/common-server";
type CreateStoreFunc = (engine: DEngineClient) => DStore;
type DendronEngineOptsV2 = {
    wsRoot: string;
    vaults: DVault[];
    forceNew?: boolean;
    createStore?: CreateStoreFunc;
    mode?: DEngineMode;
    logger?: DLogger;
    config: DendronConfig;
};
type DendronEnginePropsV2 = Required<DendronEngineOptsV2>;
export declare class DendronEngineV2 implements DEngine {
    wsRoot: string;
    store: DStore;
    logger: DLogger;
    fuseEngine: FuseEngine;
    hooks: DHookDict;
    private _vaults;
    private renderedCache;
    private schemas;
    constructor(props: DendronEnginePropsV2);
    static create({ wsRoot, logger }: {
        logger?: DLogger;
        wsRoot: string;
    }): DendronEngineV2;
    /**
     * @deprecated
     * For accessing a specific note by id, see {@link DendronEngineV2.getNote}.
     * If you need all notes, avoid modifying any note as this will cause unintended changes on the store side
     */
    get notes(): NotePropsByIdDict;
    /**
     * @deprecated see {@link DendronEngineV2.findNotes}
     */
    get noteFnames(): import("@saili/common-all").NotePropsByFnameDict;
    get vaults(): DVault[];
    set vaults(vaults: DVault[]);
    /**
     * Does not throw error but returns it
     */
    init(): Promise<DEngineInitResp>;
    /**
     * See {@link DEngine.getNote}
     */
    getNote(id: string): Promise<GetNoteResp>;
    getNoteMeta(id: string): Promise<GetNoteMetaResp>;
    bulkGetNotes(ids: string[]): Promise<BulkGetNoteResp>;
    bulkGetNotesMeta(ids: string[]): Promise<BulkGetNoteMetaResp>;
    /**
     * See {@link DEngine.findNotes}
     */
    findNotes(opts: FindNoteOpts): Promise<NoteProps[]>;
    /**
     * See {@link DEngine.findNotesMeta}
     */
    findNotesMeta(opts: FindNoteOpts): Promise<NotePropsMeta[]>;
    bulkWriteNotes(opts: BulkWriteNotesOpts): Promise<import("@saili/common-all").BulkWriteNotesResp>;
    deleteNote(id: string, opts?: EngineDeleteOpts): ReturnType<DEngineClient["deleteNote"]>;
    deleteSchema(id: string, opts?: EngineDeleteOpts): Promise<DeleteSchemaResp>;
    getSchema(id: string): Promise<GetSchemaResp>;
    info(): Promise<EngineInfoResp>;
    querySchema(queryString: string): Promise<QuerySchemaResp>;
    queryNotes(opts: QueryNotesOpts): Promise<QueryNotesResp>;
    renderNote({ id, note, flavor, dest, }: RenderNoteOpts): Promise<RenderNoteResp>;
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
    refreshNotesV2(notes: NoteChangeEntry[]): Promise<void>;
    renameNote(opts: RenameNoteOpts): Promise<RenameNoteResp>;
    updateIndex(mode: DNodeType): Promise<void>;
    writeNote(note: NoteProps, opts?: EngineWriteOptsV2): Promise<WriteNoteResp>;
    writeSchema(schema: SchemaModuleProps, opts?: EngineSchemaWriteOpts): Promise<import("@saili/common-all").WriteSchemaResp>;
    getNoteBlocks(opts: GetNoteBlocksOpts): Promise<GetNoteBlocksResp>;
    getDecorations(opts: GetDecorationsOpts): Promise<GetDecorationsResp>;
}
export declare const createEngine: ({ wsRoot }: WorkspaceOpts) => DEngineClient;
export {};
