import { URI } from "vscode-uri";
import { RespV3, SchemaModuleProps, WriteSchemaOpts } from "../types";
import { IDataStore } from "./IDataStore";
import { IFileStore } from "./IFileStore";
import { ISchemaStore } from "./ISchemaStore";
export declare class SchemaStore implements ISchemaStore<string> {
    private _fileStore;
    private _metadataStore;
    private _wsRoot;
    constructor(fileStore: IFileStore, dataStore: IDataStore<string, SchemaModuleProps>, wsRoot: URI);
    dispose(): void;
    /**
     * See {@link ISchemaStore.getMetadata}
     */
    getMetadata(key: string): Promise<RespV3<SchemaModuleProps>>;
    /**
     * See {@link ISchemaStore.bulkGetMetadata}
     */
    bulkGetMetadata(keys: string[]): Promise<RespV3<SchemaModuleProps>[]>;
    /**
     * See {@link ISchemaStore.write}
     */
    write(opts: WriteSchemaOpts<string>): Promise<RespV3<string>>;
    /**
     * See {@link ISchemaStore.writeMetadata}
     */
    writeMetadata(opts: WriteSchemaOpts<string>): Promise<RespV3<string>>;
    /**
     * See {@link ISchemaStore.bulkWriteMetadata}
     */
    bulkWriteMetadata(opts: WriteSchemaOpts<string>[]): Promise<RespV3<string>[]>;
    /**
     * See {@link ISchemaStore.delete}
     */
    delete(key: string): Promise<RespV3<string>>;
    /**
     * See {@link ISchemaStore.deleteMetadata}
     */
    deleteMetadata(key: string): Promise<RespV3<string>>;
}
