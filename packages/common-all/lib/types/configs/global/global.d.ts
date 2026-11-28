/**
 * Namespace for all global configurations.
 */
export type SailGlobalConfig = {
    enableFMTitle: boolean;
    enableNoteTitleForLink: boolean;
    enablePrettyRefs: boolean;
    enableKatex: boolean;
    enableChildLinks: boolean;
    enableBackLinks: boolean;
};
/**
 * Generates default for {@link SailGlobalConfig}
 * @returns SailGlobalConfig
 */
export declare function genDefaultGlobalConfig(): SailGlobalConfig;
