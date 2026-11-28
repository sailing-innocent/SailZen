import { SailConfigEntry, SailConfigEntryCollection } from "../../types/configs/base";
import { SailCommandConfig } from "../../types/configs/commands/commands";
import { LookupSelectionModeEnum } from "../../types/configs/commands/lookup";
import { InsertNoteIndexConfig } from "../../types/configs/commands/insertNoteIndex";
/**
 * Lookup
 */
/**
 * Selection mode entries
 */
export declare const SELECTION_MODES: Record<LookupSelectionModeEnum, SailConfigEntry<string>>;
/**
 * Insert note index
 */
/**
 * Insert note index entries
 */
export declare const INSERT_NOTE_INDEX: SailConfigEntryCollection<InsertNoteIndexConfig>;
/**
 * Command entry collection
 */
export declare const COMMANDS: SailConfigEntryCollection<SailCommandConfig>;
