import { Utils } from "vscode-uri";
import { ERROR_SEVERITY, ERROR_STATUS } from "../constants";
import { SchemaUtils } from "../dnode";
import { SailError } from "../error";
import { VaultUtils } from "../vault";
export class SchemaStore {
    _fileStore;
    _metadataStore;
    _wsRoot;
    constructor(fileStore, dataStore, wsRoot) {
        this._fileStore = fileStore;
        this._metadataStore = dataStore;
        this._wsRoot = wsRoot;
    }
    dispose() {
        this._metadataStore.dispose();
    }
    /**
     * See {@link ISchemaStore.getMetadata}
     */
    async getMetadata(key) {
        return this._metadataStore.get(key);
    }
    /**
     * See {@link ISchemaStore.bulkGetMetadata}
     */
    async bulkGetMetadata(keys) {
        return Promise.all(keys.map((key) => this.getMetadata(key)));
    }
    /**
     * See {@link ISchemaStore.write}
     */
    async write(opts) {
        const { key, schema } = opts;
        const metaResp = await this.writeMetadata({ key, schema });
        if (metaResp.error) {
            return { error: metaResp.error };
        }
        const uri = Utils.joinPath(this._wsRoot, VaultUtils.getRelPath(schema.vault), schema.fname + ".schema.yml");
        const writeResp = await this._fileStore.write(uri, SchemaUtils.serializeModuleProps(schema));
        if (writeResp.error) {
            return { error: writeResp.error };
        }
        return { data: key };
    }
    /**
     * See {@link ISchemaStore.writeMetadata}
     */
    async writeMetadata(opts) {
        const { key, schema } = opts;
        // Ids don't match, return error
        if (key !== schema.root.id) {
            return {
                error: SailError.createFromStatus({
                    status: ERROR_STATUS.WRITE_FAILED,
                    message: `Ids don't match between key ${key} and schema ${schema}.`,
                    severity: ERROR_SEVERITY.MINOR,
                }),
            };
        }
        return this._metadataStore.write(key, schema);
    }
    /**
     * See {@link ISchemaStore.bulkWriteMetadata}
     */
    async bulkWriteMetadata(opts) {
        return Promise.all(opts.map((writeMetaOpt) => {
            return this.writeMetadata(writeMetaOpt);
        }));
    }
    /**
     * See {@link ISchemaStore.delete}
     */
    async delete(key) {
        const metadata = await this.getMetadata(key);
        if (metadata.error) {
            return { error: metadata.error };
        }
        const resp = await this.deleteMetadata(key);
        if (resp.error) {
            return { error: resp.error };
        }
        const uri = Utils.joinPath(this._wsRoot, VaultUtils.getRelPath(metadata.data.vault), metadata.data.fname + ".schema.yml");
        const deleteResp = await this._fileStore.delete(uri);
        if (deleteResp.error) {
            return { error: deleteResp.error };
        }
        return { data: key };
    }
    /**
     * See {@link ISchemaStore.deleteMetadata}
     */
    async deleteMetadata(key) {
        const metadata = await this.getMetadata(key);
        if (metadata.error) {
            return { error: metadata.error };
        }
        else if (metadata.data.fname === "root") {
            return {
                error: SailError.createFromStatus({
                    status: ERROR_STATUS.CANT_DELETE_ROOT,
                    message: `Cannot delete ${key}. Root schemas cannot be deleted.`,
                    severity: ERROR_SEVERITY.MINOR,
                }),
            };
        }
        return this._metadataStore.delete(key);
    }
}
//# sourceMappingURL=SchemaStore.js.map