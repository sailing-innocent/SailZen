import _ from "lodash";
import { ResultAsync } from "neverthrow";
import { SchemaUtils } from "../dnode";
import { SailError } from "../error";
import { FuseEngine } from "../FuseEngine";
export class FuseQueryStore {
    fuseEngine;
    constructor(opts) {
        this.fuseEngine = new FuseEngine({
            fuzzThreshold: _.defaults(opts, { fuzzThreshold: 0.2 }).fuzzThreshold,
        });
    }
    addSchemaToIndex(schema) {
        return ResultAsync.fromPromise(Promise.resolve(this.fuseEngine.schemaIndex.add(SchemaUtils.getModuleRoot(schema))), (err) => new SailError({
            message: "issue adding schema to index",
            innerError: err,
        }));
    }
    queryNotes(qs, opts) {
        const items = this.fuseEngine.queryNote({
            qs,
            ...opts,
        });
        return ResultAsync.fromSafePromise(Promise.resolve(items));
    }
    querySchemas(qs) {
        const schemaIds = this.fuseEngine.querySchema({ qs });
        return ResultAsync.fromSafePromise(Promise.resolve(schemaIds));
    }
    removeSchemaFromIndex(schema) {
        this.fuseEngine.removeSchemaFromIndex(schema);
        return ResultAsync.fromSafePromise(Promise.resolve());
    }
    replaceNotesIndex(props) {
        return ResultAsync.fromPromise(this.fuseEngine.replaceNotesIndex(props), (err) => new SailError({
            message: "issue replacing index",
            innerError: err,
        }));
    }
    replaceSchemasIndex(props) {
        return ResultAsync.fromPromise(this.fuseEngine.replaceSchemaIndex(props), (err) => new SailError({
            message: "issue replacing index",
            innerError: err,
        }));
    }
    updateNotesIndex(changes) {
        return ResultAsync.fromPromise(
        // return signature requires us to return void vs void[]
        this.fuseEngine.updateNotesIndex(changes).then(() => { }), (err) => new SailError({
            message: "issue updating index",
            innerError: err,
        }));
    }
    updateSchemasIndex() {
        throw new Error("Method not implemented.");
    }
}
//# sourceMappingURL=FuseMetadataStore.js.map