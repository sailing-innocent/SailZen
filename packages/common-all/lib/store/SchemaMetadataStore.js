import _ from "lodash";
import { ERROR_SEVERITY, ERROR_STATUS } from "../constants";
import { SailError } from "../error";
export class SchemaMetadataStore {
    /**
     * Map of schema root id -> SchemaModuleProps
     */
    _schemaMetadataById;
    constructor() {
        this._schemaMetadataById = {};
    }
    dispose() {
        this._schemaMetadataById = {};
    }
    /**
     * See {@link IDataStore.get}
     */
    async get(key) {
        const maybeSchema = this._schemaMetadataById[key];
        if (maybeSchema) {
            return { data: _.cloneDeep(maybeSchema) };
        }
        else {
            return {
                error: SailError.createFromStatus({
                    status: ERROR_STATUS.CONTENT_NOT_FOUND,
                    message: `SchemaModuleProps not found for key ${key}.`,
                    severity: ERROR_SEVERITY.MINOR,
                }),
            };
        }
    }
    async find(_opts) {
        throw new Error("Method not implemented.");
    }
    /**
     * See {@link IDataStore.write}
     *
     * Add schema to _schemaMetadataById. If schema root id already exists, override existing schema
     */
    async write(key, data) {
        this._schemaMetadataById[data.root.id] = data;
        return { data: key };
    }
    /**
     * See {@link IDataStore.delete}
     *
     * Remove schema from both _schemaMetadataById.
     */
    async delete(key) {
        delete this._schemaMetadataById[key];
        return { data: key };
    }
}
//# sourceMappingURL=SchemaMetadataStore.js.map