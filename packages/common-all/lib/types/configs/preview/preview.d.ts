import { Theme } from "../publishing";
/**
 * Namespace for all preview related configurations
 */
export type SailPreviewConfig = {
    enableFMTitle: boolean;
    enableNoteTitleForLink: boolean;
    enableFrontmatterTags: boolean;
    enableHashesForFMTags: boolean;
    enablePrettyRefs: boolean;
    enableKatex: boolean;
    automaticallyShowPreview: boolean;
    theme?: Theme;
};
/**
 * Generate defaults for {@link SailPreviewConfig}
 * @returns SailPreviewConfig
 */
export declare function genDefaultPreviewConfig(): SailPreviewConfig;
