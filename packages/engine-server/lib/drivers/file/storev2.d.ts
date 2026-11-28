import { BulkWriteNotesOpts, DeleteSchemaResp, DendronCompositeError, DendronError, DEngineClient, DNoteAnchorPositioned, DStore, DVault, EngineDeleteOpts, EngineSchemaWriteOpts, EngineUpdateNodesOptsV2, EngineWriteOptsV2, FindNoteOpts, GetSchemaResp, IDendronError, DendronConfig, NoteChangeEntry, NoteChangeUpdateEntry, NoteProps, NotePropsByFnameDict, NotePropsByIdDict, NotesCacheEntryMap, RenameNoteOpts, RespV3, RespWithOptError, SchemaModuleDict, SchemaModuleProps, StoreV2InitResp, WriteNoteResp, WriteSchemaResp } from "@saili/common-all";
import { DLogger } from "@saili/common-server";
export type DEngineInitSchemaResp = RespWithOptError<SchemaModuleProps[]>;
export declare class FileStorage implements DStore {
    vaults: DVault[];
    /**
     * Warning: currently this note dictionary contains backlink data that gets
     * populated upon initialization. However, the update note operations do not change
     * the backlink data in this dictionary hence it starts to contain stale backlink data.
     *  */
    notes: NotePropsByIdDict;
    noteFnames: NotePropsByFnameDict;
    schemas: SchemaModuleDict;
    logger: DLogger;
    anchors: DNoteAnchorPositioned[];
    wsRoot: string;
    config: DendronConfig;
    private engine;
    constructor(props: {
        engine: DEngineClient;
        logger: DLogger;
        config: DendronConfig;
    });
    init(): Promise<StoreV2InitResp>;
    static createMalformedSchemaError(resp: DEngineInitSchemaResp): DendronError<import("@saili/common-all").StatusCodes | undefined>;
    /**
     * See {@link DStore.getNote}
     */
    getNote(id: string): Promise<RespV3<NoteProps>>;
    /**
     * See {@link DStore.findNotes}
     */
    findNotes(opts: FindNoteOpts): Promise<NoteProps[]>;
    /**
     *
     * @param id id of note to be deleted
     * @returns
     */
    deleteNote(id: string, opts?: EngineDeleteOpts): Promise<NoteChangeEntry[]>;
    getSchema(id: string): Promise<GetSchemaResp>;
    deleteSchema(id: string, opts?: EngineDeleteOpts): Promise<DeleteSchemaResp>;
    initSchema(): Promise<DEngineInitSchemaResp>;
    _initSchema(vault: DVault): Promise<{
        data: SchemaModuleProps[];
        errors: any[];
    }>;
    initNotes(): Promise<{
        errors: IDendronError[];
    }>;
    /** Adds backlinks mutating 'allNotes' argument in place. */
    private _addBacklinks;
    private _addBacklinksImpl;
    private _addLinkCandidates;
    _initNotes(vault: DVault): Promise<{
        notesById: NotePropsByIdDict;
        cacheUpdates: NotesCacheEntryMap;
        errors: IDendronError[];
    }>;
    bulkWriteNotes(opts: BulkWriteNotesOpts): Promise<{
        data: NoteChangeEntry[];
        error?: undefined;
    } | {
        error: DendronCompositeError | undefined;
        data: ({
            note: NoteProps;
            status: "create" | "delete";
        } | NoteChangeUpdateEntry)[];
    }>;
    private referenceRangeParts;
    /**
     * Update the links inside this note that need to be updated for the rename from `oldLoc` to `newLoc`
     * Will update the note in place
     */
    private processNoteChangedByRename;
    renameNote(opts: RenameNoteOpts): Promise<NoteChangeEntry[]>;
    /**
     * Update a note.
     *
     * If {@link newNode} is set, set the {@link NoteProps["parent"]} property and create stubs as necessary
     *
     * @param note
     * @param opts
     * @returns
     */
    updateNote(note: NoteProps, opts?: EngineUpdateNodesOptsV2): Promise<{
        error: any;
        data?: undefined;
    } | {
        data: NoteChangeEntry[];
        error: null;
    }>;
    /**
     * Write a new note. Also take care of updating logic of parents and children if new note replaces an existing note that has a different id.
     * If the existing and new note have the same id, then do nothing.
     *
     * @param param0
     * @returns - Changed Entries
     */
    private _writeNewNote;
    writeNote(note: NoteProps, opts?: EngineWriteOptsV2): Promise<WriteNoteResp>;
    writeSchema(schemaModule: SchemaModuleProps, opts?: EngineSchemaWriteOpts): Promise<WriteSchemaResp>;
    /**
     * Create backlink from given link that references another note (denoted by presence of link.to field)
     * and add that backlink to referenced note's links
     *
     * @param link Link potentionally referencing another note
     */
    private addBacklink;
    /**
     * Remove backlink associated with given link that references another note (denoted by presence of link.to field)
     * from that referenced note
     *
     * @param link Link potentionally referencing another note
     */
    private removeBacklink;
}
