import { genDefaultCommandConfig, } from "./commands/commands";
import { genDefaultWorkspaceConfig, } from "./workspace/SailWorkspaceConfig";
import { genDefaultPreviewConfig, } from "./preview/preview";
import { genDefaultPublishingConfig, } from "./publishing/publishing";
import { genDefaultDevConfig } from "./dev/SailDevConfig";
/**
 * Generates a default SailConfig using
 * respective default config generators of each sub config groups.
 * @returns SailConfig
 */
export function genDefaultSailConfig() {
    return {
        version: 5,
        commands: genDefaultCommandConfig(),
        workspace: genDefaultWorkspaceConfig(),
        preview: genDefaultPreviewConfig(),
        publishing: genDefaultPublishingConfig(),
        dev: genDefaultDevConfig(),
    };
}
//# sourceMappingURL=sailConfig.js.map