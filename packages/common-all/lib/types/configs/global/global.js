/**
 * Generates default for {@link SailGlobalConfig}
 * @returns SailGlobalConfig
 */
export function genDefaultGlobalConfig() {
    return {
        enableFMTitle: true, // TODO: split implementation to respect non-global config
        enableNoteTitleForLink: true, // TODO: split
        enableKatex: true,
        enablePrettyRefs: true,
        enableChildLinks: true,
        enableBackLinks: true,
    };
}
//# sourceMappingURL=global.js.map