import { DLogger } from "../DLogger";
import { INoteStore, IQueryStore } from "../store";
import { BulkGetNoteMetaResp, BulkGetNoteResp, BulkWriteNotesOpts, BulkWriteNotesResp, DeleteNoteResp, DLink, EngineDeleteOpts, EngineWriteOptsV2, FindNotesMetaResp, FindNotesResp, GetNoteMetaResp, GetNoteResp, NoteChangeEntry, NoteProps, NotePropsMeta, QueryNotesOpts, QueryNotesResp, ReducedDEngine, RenameNoteOpts, RenameNoteResp, RespV3, WriteNoteResp } from "../types";
import { DVault } from "../types/DVault";
import { FindNoteOpts } from "../types/FindNoteOpts";
/**
 * Abstract base class that contains common logic between SailEngine and
 * SailEngineWeb
 */
export declare abstract class EngineV3Base implements ReducedDEngine {
    protected noteStore: INoteStore<string>;
    protected queryStore: IQueryStore;
    protected logger: DLogger;
    vaults: DVault[];
    wsRoot: string;
    constructor(opts: {
        noteStore: INoteStore<string>;
        queryStore: IQueryStore;
        logger: DLogger;
        vaults: DVault[];
        wsRoot: string;
    });
    /**
     * See {@link DEngine.getNote}
     */
    getNote(id: string): Promise<GetNoteResp>;
    /**
     * See {@link DEngine.getNoteMeta}
     */
    getNoteMeta(id: string): Promise<GetNoteMetaResp>;
    /**
     * See {@link DEngine.bulkGetNotes}
     */
    bulkGetNotes(ids: string[]): Promise<BulkGetNoteResp>;
    /**
     * See {@link DEngine.bulkGetNotesMeta}
     */
    bulkGetNotesMeta(ids: string[]): Promise<BulkGetNoteMetaResp>;
    /**
     * See {@link DEngine.findNotes}
     */
    findNotes(opts: FindNoteOpts): Promise<FindNotesResp>;
    /**
     * See {@link DEngine.findNotesMeta}
     */
    findNotesMeta(opts: FindNoteOpts): Promise<FindNotesMetaResp>;
    /**
     * See {@link DEngine.bulkWriteNotes}
     */
    bulkWriteNotes(opts: BulkWriteNotesOpts): Promise<BulkWriteNotesResp>;
    /**
     * See {@link DEngine.deleteNote}
     */
    deleteNote(id: string, opts?: EngineDeleteOpts): Promise<DeleteNoteResp>;
    queryNotes(opts: QueryNotesOpts): Promise<QueryNotesResp>;
    /**
     * See {@link DEngine.renameNote}
     */
    abstract renameNote(opts: RenameNoteOpts): Promise<RenameNoteResp>;
    /**
     * See {@link DEngine.writeNote}
     */
    abstract writeNote(note: NoteProps, opts?: EngineWriteOptsV2): Promise<WriteNoteResp>;
    /**
     * Move children of old parent note to new parent
     * @return note change entries of modified children
     */
    protected updateChildrenWithNewParent(oldParent: NotePropsMeta, newParent: NotePropsMeta): Promise<NoteChangeEntry[]>;
    /**
     * Update note metadata store based on note change entries
     * @param changes entries to update
     * @returns
     */
    protected updateNoteMetadataStore(changes: NoteChangeEntry[]): Promise<RespV3<string>[]>;
    /**
     * Create backlink from given link that references another note (denoted by presence of link.to field)
     * and add that backlink to referenced note's links
     *
     * @param link Link potentionally referencing another note
     */
    protected addBacklink(link: DLink): Promise<NoteChangeEntry[]>;
    /**
     * Remove backlink associated with given link that references another note (denoted by presence of link.to field)
     * from that referenced note
     *
     * @param link Link potentially referencing another note
     */
    protected removeBacklink(link: DLink): Promise<NoteChangeEntry[]>;
}
