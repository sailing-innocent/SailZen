import { Theme } from "../publishing";

/**
 * Namespace for all preview related configurations
 */
export type SailPreviewConfig = {
  enableFMTitle: boolean; // TODO: split
  enableNoteTitleForLink: boolean; // TODO: split
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
export function genDefaultPreviewConfig(): SailPreviewConfig {
  return {
    enableFMTitle: true,
    enableNoteTitleForLink: true,
    enableFrontmatterTags: true,
    enableHashesForFMTags: false,
    enablePrettyRefs: true,
    enableKatex: true,
    automaticallyShowPreview: false,
  };
}
