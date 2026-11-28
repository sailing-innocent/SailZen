import { NoteAddBehaviorEnum } from "./types";
/**
 * Namespace for configuring journal note behavior
 */
export type JournalConfig = {
    dailyDomain: string;
    dailyVault?: string;
    name: string;
    dateFormat: string;
    addBehavior: NoteAddBehaviorEnum;
};
declare const possibleDayOfWeekNumber: readonly [0, 1, 2, 3, 4, 5, 6];
export type dayOfWeekNumber = typeof possibleDayOfWeekNumber[number];
/**
 * Generates default {@link JournalConfig}
 * @returns JouranlConfig
 */
export declare function genDefaultJournalConfig(): JournalConfig;
export {};
