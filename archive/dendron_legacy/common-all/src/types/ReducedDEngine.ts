import { DEngine } from "./types";

/**
 * Subset of DEngine capabilities designed to support Sail as a Web Extension
 */
export type ReducedDEngine = Pick<
  DEngine,
  | "wsRoot"
  | "getNote"
  | "getNoteMeta"
  | "bulkGetNotes"
  | "bulkGetNotesMeta"
  | "findNotes"
  | "findNotesMeta"
  | "deleteNote"
  | "bulkWriteNotes"
  | "writeNote"
  | "renameNote"
  | "queryNotes"
>;
