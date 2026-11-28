import { genDefaultJournalConfig } from "./journal";
import { genDefaultScratchConfig } from "./scratch";
import { genDefaultGraphConfig } from "./graph";
import { VaultSyncModeEnum } from "../base";
import { genDefaultTaskConfig } from "./task";
/**
 * Generates default {@link SailWorkspaceConfig}
 * @returns SailWorkspaceConfig
 */
export function genDefaultWorkspaceConfig() {
    return {
        vaults: [],
        journal: genDefaultJournalConfig(),
        scratch: genDefaultScratchConfig(),
        task: genDefaultTaskConfig(),
        graph: genDefaultGraphConfig(),
        enableAutoCreateOnDefinition: false,
        enableXVaultWikiLink: false,
        enableRemoteVaultInit: true,
        enableZDocTags: true,
        enableHashTags: true,
        workspaceVaultSyncMode: VaultSyncModeEnum.noCommit,
        enableAutoFoldFrontmatter: false,
        enableEditorDecorations: true,
        maxPreviewsCached: 10,
        maxNoteLength: 204800,
        enableFullHierarchyNoteTitle: false,
        enablePersistentHistory: false,
    };
}
//# sourceMappingURL=SailWorkspaceConfig.js.map