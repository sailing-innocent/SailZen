/**
 * Enum definition of possible lookup selection behavior values
 */
export declare enum LookupSelectionModeEnum {
    extract = "extract",
    link = "link",
    none = "none"
}
export declare enum LookupSelectVaultModeOnCreateEnum {
    smart = "smart",
    alwaysPrompt = "alwaysPrompt"
}
/**
 * String literal type generated from {@link NoteLookupSelectionBehaviorEnum}
 */
export type LookupSelectionMode = keyof typeof LookupSelectionModeEnum;
export type LookupSelectVaultModeOnCreate = keyof typeof LookupSelectVaultModeOnCreateEnum;
/**
 * Namespace for configuring lookup commands
 */
export type LookupConfig = {
    note: NoteLookupConfig;
};
/**
 * Namespace for configuring {@link NoteLookupCommand}
 */
export type NoteLookupConfig = {
    selectionMode: LookupSelectionMode;
    vaultSelectionModeOnCreate: LookupSelectVaultModeOnCreate;
    confirmVaultOnCreate: boolean;
    leaveTrace: boolean;
    bubbleUpCreateNew: boolean;
    fuzzThreshold: number;
};
/**
 * Generates default {@link LookupConfig}
 * @returns LookupConfig
 */
export declare function genDefaultLookupConfig(): LookupConfig;
