import { JournalConfig } from "./journal";
/**
 * Namespace for configuring scratch note behavior
 */
export type ScratchConfig = Pick<JournalConfig, "name" | "dateFormat" | "addBehavior">;
/**
 * Generates default {@link ScratchConfig}
 * @returns ScratchConfig
 */
export declare function genDefaultScratchConfig(): ScratchConfig;
