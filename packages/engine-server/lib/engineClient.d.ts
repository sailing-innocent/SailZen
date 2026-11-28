import { BulkGetNoteMetaResp, BulkGetNoteResp, BulkWriteNotesOpts, DeleteNoteResp, DeleteSchemaResp, SailAPI, DEngineClient, DEngineInitResp, DHookDict, DVault, EngineDeleteOpts, EngineEventEmitter, EngineInfoResp, EngineInitOpts, EngineState, EngineInitStatus, EngineSchemaWriteOpts, EngineWriteOptsV2, Event, FindNoteOpts, FuseEngine, GetDecorationsOpts, GetDecorationsResp, GetNoteBlocksOpts, GetNoteBlocksResp, GetNoteMetaResp, GetNoteResp, GetSchemaResp, NoteChangeEntry, NoteProps, NotePropsByFnameDict, NotePropsByIdDict, NotePropsMeta, QueryNotesOpts, QuerySchemaResp, RenameNoteOpts, RenameNoteResp, RenderNoteOpts, SchemaModuleProps, WriteNoteResp, WriteSchemaResp, QueryNotesResp } from "@saili/common-all";
import { DLogger } from "@saili/common-server";
import { HistoryService } from "./history";
type SailEngineClientOpts = {
    vaults: DVault[];
    ws: string;
};
export declare class SailEngineClient implements DEngineClient, EngineEventEmitter {
    private _onNoteChangedEmitter;
    private _config;
    /**
     * Last known engine state, based on init responses and status polls.
     * Responses from older servers that don't report a state are treated as
     * ready (full init semantics).
     */
    private _engineState;
    notes: NotePropsByIdDict;
    noteFnames: NotePropsByFnameDict;
    wsRoot: string;
    ws: string;
    fuseEngine: FuseEngine;
    api: SailAPI;
    vaults: DVault[];
    history?: HistoryService;
    logger: DLogger;
    hooks: DHookDict;
    static create({ port, vaults, ws, history, logger, }: {
        port: number | string;
        history?: HistoryService;
        logger?: DLogger;
    } & SailEngineClientOpts): SailEngineClient;
    static getPort({ wsRoot }: {
        wsRoot: string;
    }): number;
    constructor({ api, vaults, ws, history, logger, }: {
        api: SailAPI;
        history?: HistoryService;
        logger?: DLogger;
    } & SailEngineClientOpts);
    /**
     * Event that fires upon the changing of note state in the engine after a set
     * of NoteProps has been changed AND those changes have been reflected on the
     * engine side. Note creation, deletion, and updates are all fired from this
     * event.
     */
    get onEngineNoteStateChanged(): Event<NoteChangeEntry[]>;
    dispose(): void;
    /** Last known engine lifecycle state reported by the server. */
    getEngineState(): EngineState;
    /**
     * Poll the server for the current engine init status. Used during
     * fast-first startup while the full index runs in the background.
     */
    fetchInitStatus(): Promise<EngineInitStatus>;
    /**
     * Load all nodes
     */
    init(opts?: EngineInitOpts): Promise<DEngineInitResp>;
    /**
     * See {@link DStore.getNote}
     */
    getNote(id: string): Promise<GetNoteResp>;
    getNoteMeta(id: string): Promise<GetNoteMetaResp>;
    bulkGetNotes(ids: string[]): Promise<BulkGetNoteResp>;
    bulkGetNotesMeta(ids: string[]): Promise<BulkGetNoteMetaResp>;
    /**
     * See {@link DStore.findNotes}
     */
    findNotes(opts: FindNoteOpts): Promise<NoteProps[]>;
    /**
     * See {@link DStore.findNotesMeta}
     */
    findNotesMeta(opts: FindNoteOpts): Promise<NotePropsMeta[]>;
    bulkWriteNotes(opts: BulkWriteNotesOpts): Promise<import("@saili/common-all").BulkWriteNotesResp>;
    deleteNote(id: string, opts?: EngineDeleteOpts): Promise<DeleteNoteResp>;
    deleteSchema(id: string, opts?: EngineDeleteOpts): Promise<DeleteSchemaResp>;
    info(): Promise<EngineInfoResp>;
    queryNotes(opts: QueryNotesOpts): Promise<QueryNotesResp>;
    renderNote(opts: RenderNoteOpts): Promise<import("@saili/common-all").RenderNoteResp>;
    refreshNotesV2(notes: NoteChangeEntry[]): Promise<void>;
    /** Renames the note.
     *
     *  WARNING: When doing bulk operations. Do not invoke multiple requests to this
     *  command in parallel, wait for a single call to finish before requesting another call.
     *  Otherwise some race condition starts to cause intermittent failures.
     *  */
    renameNote(opts: RenameNoteOpts): Promise<RenameNoteResp>;
    sync(): Promise<DEngineInitResp>;
    writeNote(note: NoteProps, opts?: EngineWriteOptsV2): Promise<WriteNoteResp>;
    getSchema(id: string): Promise<GetSchemaResp>;
    querySchema(qs: string): Promise<QuerySchemaResp>;
    writeSchema(schema: SchemaModuleProps, opts?: EngineSchemaWriteOpts): Promise<WriteSchemaResp>;
    getNoteBlocks({ id, filterByAnchorType, }: GetNoteBlocksOpts): Promise<GetNoteBlocksResp>;
    getDecorations(opts: GetDecorationsOpts): Promise<GetDecorationsResp>;
}
export {};
