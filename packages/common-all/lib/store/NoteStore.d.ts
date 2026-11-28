import { URI } from "vscode-uri";
import { DNoteLoc, NoteProps, NotePropsMeta, RespV3, WriteNoteMetaOpts, WriteNoteOpts } from "../types";
import { FindNoteOpts } from "../types/FindNoteOpts";
import { IDataStore } from "./IDataStore";
import { IFileStore } from "./IFileStore";
import { INoteStore } from "./INoteStore";
/**
 * Responsible for storing NoteProps non-metadata and NoteProps metadata
 */
export declare class NoteStore implements INoteStore<string> {
    private _fileStore;
    private _metadataStore;
    private _wsRoot;
    constructor(fileStore: IFileStore, dataStore: IDataStore<string, NotePropsMeta>, wsRoot: URI);
    dispose(): void;
    /**
     * See {@link INoteStore.get}
     */
    get(key: string): Promise<RespV3<NoteProps>>;
    /**
     * See {@link INoteStore.bulkGet}
     */
    bulkGet(keys: string[]): Promise<RespV3<NoteProps>[]>;
    /**
     * See {@link INoteStore.getMetadata}
     */
    getMetadata(key: string): Promise<RespV3<NotePropsMeta>>;
    /**
     * See {@link INoteStore.bulkGetMetadata}
     */
    bulkGetMetadata(keys: string[]): Promise<RespV3<NotePropsMeta>[]>;
    /**
     * See {@link INoteStore.find}
     */
    find(opts: FindNoteOpts): Promise<RespV3<NoteProps[]>>;
    /**
     * See {@link INoteStore.findMetaData}
     */
    findMetaData(opts: FindNoteOpts): Promise<RespV3<NotePropsMeta[]>>;
    /**
     * See {@link INoteStore.write}
     */
    write(opts: WriteNoteOpts<string>): Promise<RespV3<string>>;
    /**s
     * See {@link INoteStore.writeMetadata}
     */
    writeMetadata(opts: WriteNoteMetaOpts<string>): Promise<RespV3<string>>;
    /**
     * See {@link INoteStore.bulkWriteMetadata}
     */
    bulkWriteMetadata(opts: WriteNoteMetaOpts<string>[]): Promise<RespV3<string>[]>;
    /**
     * See {@link INoteStore.delete}
     */
    delete(key: string): Promise<RespV3<string>>;
    /**
     * See {@link INoteStore.deleteMetadata}
     */
    deleteMetadata(key: string): Promise<RespV3<string>>;
    rename(oldLoc: DNoteLoc, newLoc: DNoteLoc): Promise<RespV3<string>>;
}
