import {
  SailCommandConfig,
  genDefaultCommandConfig,
} from "./commands/commands";
import {
  SailWorkspaceConfig,
  genDefaultWorkspaceConfig,
} from "./workspace/SailWorkspaceConfig";
import {
  SailPreviewConfig,
  genDefaultPreviewConfig,
} from "./preview/preview";
import {
  SailPublishingConfig,
  genDefaultPublishingConfig,
} from "./publishing/publishing";
import { SailGlobalConfig } from "./global/global";
import { SailDevConfig, genDefaultDevConfig } from "./dev/SailDevConfig";

/**
 * SailConfig
 * This is the top level config that will hold everything.
 */
export type SailConfig = {
  version: number;
  global?: SailGlobalConfig;
  commands: SailCommandConfig;
  workspace: SailWorkspaceConfig;
  preview: SailPreviewConfig;
  publishing: SailPublishingConfig;
  dev?: SailDevConfig;
};

export type TopLevelSailConfig = keyof SailConfig;

/**
 * Generates a default SailConfig using
 * respective default config generators of each sub config groups.
 * @returns SailConfig
 */
export function genDefaultSailConfig(): SailConfig {
  return {
    version: 5,
    commands: genDefaultCommandConfig(),
    workspace: genDefaultWorkspaceConfig(),
    preview: genDefaultPreviewConfig(),
    publishing: genDefaultPublishingConfig(),
    dev: genDefaultDevConfig(),
  };
}
