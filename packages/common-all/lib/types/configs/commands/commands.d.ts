import { CopyNoteLinkConfig } from ".";
import { InsertNoteIndexConfig } from "./insertNoteIndex";
import { InsertNoteLinkConfig } from "./insertNoteLink";
import { LookupConfig } from "./lookup";
import { RandomNoteConfig } from "./randomNote";
/**
 * Namespace for all command related configurations
 */
export type SailCommandConfig = {
    lookup: LookupConfig;
    randomNote: RandomNoteConfig;
    insertNoteLink: InsertNoteLinkConfig;
    insertNoteIndex: InsertNoteIndexConfig;
    copyNoteLink: CopyNoteLinkConfig;
    /**
     * Default template hiearchy used when running commands like `Apply template`
     */
    templateHierarchy?: string;
};
/**
 * Generates default {@link SailCommandConfig} using
 * respective default config generators that each command config implements.
 * @returns SailCommandConfig
 */
export declare function genDefaultCommandConfig(): SailCommandConfig;
