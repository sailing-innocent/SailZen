import { DVault, SailConfig, NoteDicts, NoteProps, ReducedDEngine } from "@saili/common-all";
/**
 * For a given note to process with unified, this function determines all
 * NoteProp dependencies that will be needed in order to parse/render the note.
 * It then creates a set of NoteDicts containing all dependencies and returns
 * it. Any nested/recursive dependencies, such as with note references, will
 * also be included.
 * @param noteToProcess
 * @param engine
 * @param config
 * @param vaults
 * @returns
 */
export declare function getParsingDependencyDicts(noteToProcess: NoteProps, engine: ReducedDEngine, config: SailConfig, vaults: DVault[]): Promise<NoteDicts>;
