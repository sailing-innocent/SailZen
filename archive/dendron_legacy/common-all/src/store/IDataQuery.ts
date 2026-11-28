import { ResultAsync } from "neverthrow";
import {
  SailError,
  NoteChangeEntry,
  NotePropsByIdDict,
  NotePropsMeta,
  SchemaModuleDict,
  SchemaModuleProps,
} from "..";

export type INoteQueryOpts = {
  /**
   * Original query string (which can contain minor modifications such as mapping '/'->'.')
   * This string is added for sorting the lookup results when there is exact match with
   * original query. */
  originalQS: string;
  onlyDirectChildren?: boolean;
};

export interface IQueryStore {
  queryNotes(
    qs: string,
    opts: INoteQueryOpts
  ): ResultAsync<NotePropsMeta[], SailError>;
  querySchemas(
    qs: string,
    opts?: INoteQueryOpts
  ): ResultAsync<{ id: string }[], SailError>;
  updateNotesIndex(changes: NoteChangeEntry[]): ResultAsync<void, SailError>;
  updateSchemasIndex(): ResultAsync<void, SailError>;
  replaceNotesIndex(props: NotePropsByIdDict): ResultAsync<void, SailError>;
  replaceSchemasIndex(props: SchemaModuleDict): ResultAsync<void, SailError>;

  removeSchemaFromIndex(
    schema: SchemaModuleProps
  ): ResultAsync<void, SailError>;

  addSchemaToIndex(schema: SchemaModuleProps): ResultAsync<void, SailError>;
}
