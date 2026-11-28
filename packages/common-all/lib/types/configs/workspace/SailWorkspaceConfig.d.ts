import { JournalConfig } from "./journal";
import { ScratchConfig } from "./scratch";
import { SailGraphConfig } from "./graph";
import { SeedSite } from "../../seed";
import { DHookDict } from "../../hooks";
import { VaultSyncMode } from "../base";
import { TaskConfig } from "./task";
import { DVault } from "../../DVault";
import { SailWorkspaceEntry } from "../../SailWorkspaceEntry";
/**
 * Namespace for configurations that affect the workspace
 */
export type SailWorkspaceConfig = {
    sailVersion?: string;
    workspaces?: {
        [key: string]: SailWorkspaceEntry | undefined;
    };
    seeds?: {
        [key: string]: SailSeedEntry | undefined;
    };
    vaults: DVault[];
    hooks?: DHookDict;
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
    maxPreviewsCached: number;
    maxNoteLength: number;
    enableEditorDecorations: boolean;
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
export declare function genDefaultWorkspaceConfig(): SailWorkspaceConfig;
