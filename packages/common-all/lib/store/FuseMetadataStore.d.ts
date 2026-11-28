import { StatusCodes } from "http-status-codes";
import { ResultAsync } from "neverthrow";
import { SailError } from "../error";
import { FuseEngine } from "../FuseEngine";
import { NoteChangeEntry, NotePropsByIdDict, NotePropsMeta, SchemaModuleDict, SchemaModuleProps } from "../types";
import { INoteQueryOpts, IQueryStore } from "./IDataQuery";
export declare class FuseQueryStore implements IQueryStore {
    fuseEngine: FuseEngine;
    constructor(opts?: {
        fuzzThreshold: number;
    });
    addSchemaToIndex(schema: SchemaModuleProps): ResultAsync<void, SailError<StatusCodes | undefined>>;
    queryNotes(qs: string, opts: INoteQueryOpts): ResultAsync<NotePropsMeta[], SailError<StatusCodes | undefined>>;
    querySchemas(qs: string): ResultAsync<{
        id: string;
    }[], SailError<StatusCodes | undefined>>;
    removeSchemaFromIndex(schema: SchemaModuleProps): ResultAsync<void, SailError>;
    replaceNotesIndex(props: NotePropsByIdDict): ResultAsync<void, SailError>;
    replaceSchemasIndex(props: SchemaModuleDict): ResultAsync<void, SailError>;
    updateNotesIndex(changes: NoteChangeEntry[]): ResultAsync<void, SailError>;
    updateSchemasIndex(): ResultAsync<void, SailError<StatusCodes | undefined>>;
}
