import { genDefaultJournalConfig, JournalConfig } from "./journal";
import { genDefaultScratchConfig, ScratchConfig } from "./scratch";
import { genDefaultGraphConfig, SailGraphConfig } from "./graph";
import { SeedSite } from "../../seed";
import { DHookDict } from "../../hooks";
import { VaultSyncMode, VaultSyncModeEnum } from "../base";
import { genDefaultTaskConfig, TaskConfig } from "./task";
import { DVault } from "../../DVault";
import { SailWorkspaceEntry } from "../../SailWorkspaceEntry";

/**
 * Namespace for configurations that affect the workspace
 */
export type SailWorkspaceConfig = {
  // general
  sailVersion?: string;
  workspaces?: { [key: string]: SailWorkspaceEntry | undefined };
  seeds?: { [key: string]: SailSeedEntry | undefined };
  vaults: DVault[];
  hooks?: DHookDict;
  // features
  journal: JournalConfig;
  scratch: ScratchConfig;
  task: TaskConfig;
  graph: SailGraphConfig;
  disableTelemetry?: boolean;
  enableAutoCreateOnDefinition: boolean;
  enableXVaultWikiLink: boolean;
  enableRemoteVaultInit: boolean;
  workspaceVaultSyncMode: VaultSyncMode;
  enableAutoFoldFrontmatter: boolean;
  enableZDocTags: boolean;
  enableHashTags: boolean;
  enableFullHierarchyNoteTitle: boolean;
  // performance related
  maxPreviewsCached: number;
  maxNoteLength: number;
  enableEditorDecorations: boolean;
  //
  feedback?: boolean;
  apiEndpoint?: string;
  metadataStore?: "sqlite" | "json";
  enablePersistentHistory?: boolean;
  mainVault?: string;
  enablePerfMode?: boolean;
};

export type SailSeedEntry = {
  branch?: string;
  site?: SeedSite;
};

/**
 * Generates default {@link SailWorkspaceConfig}
 * @returns SailWorkspaceConfig
 */
export function genDefaultWorkspaceConfig(): SailWorkspaceConfig {
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
