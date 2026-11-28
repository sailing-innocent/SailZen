import { RespV3, SchemaModuleProps } from "../types";
import { IDataStore } from "./IDataStore";
export declare class SchemaMetadataStore implements IDataStore<string, SchemaModuleProps> {
    /**
     * Map of schema root id -> SchemaModuleProps
     */
    private _schemaMetadataById;
    constructor();
    dispose(): void;
    /**
     * See {@link IDataStore.get}
     */
    get(key: string): Promise<RespV3<SchemaModuleProps>>;
    find(_opts: any): Promise<RespV3<SchemaModuleProps[]>>;
    /**
     * See {@link IDataStore.write}
     *
     * Add schema to _schemaMetadataById. If schema root id already exists, override existing schema
     */
    write(key: string, data: SchemaModuleProps): Promise<RespV3<string>>;
    /**
     * See {@link IDataStore.delete}
     *
     * Remove schema from both _schemaMetadataById.
     */
    delete(key: string): Promise<RespV3<string>>;
}
