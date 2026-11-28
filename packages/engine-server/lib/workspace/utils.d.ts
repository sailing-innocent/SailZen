import { DVault, DWorkspaceV2, SailConfig, NoteProps, RespV3, WorkspaceFolderCode, WorkspaceOpts, WorkspaceSettings, WorkspaceType } from "@saili/common-all";
import { URI } from "vscode-uri";
import { SyncActionResult, SyncActionStatus } from "./workspaceServiceInterface";
export declare class WorkspaceUtils {
    static isWorkspaceConfig(val: any): val is WorkspaceSettings;
    static getCodeWorkspaceSettings(wsRoot: string): Promise<RespV3<WorkspaceSettings>>;
    static getCodeWorkspaceSettingsSync(wsRoot: string): RespV3<WorkspaceSettings>;
    /** Finds the workspace type using the VSCode plugin workspace variables. */
    static getWorkspaceType({ workspaceFolders, workspaceFile, }: {
        workspaceFolders?: readonly WorkspaceFolderCode[];
        workspaceFile?: URI;
    }): Promise<WorkspaceType>;
    /** Finds the workspace type by analyzing the given directory. Use if plugin is not available.
     * @returns WorkspaceType
     */
    static getWorkspaceTypeFromDir(dir: string): Promise<WorkspaceType>;
    static updateCodeWorkspaceSettings({ wsRoot, updateCb, }: {
        wsRoot: string;
        updateCb: (settings: WorkspaceSettings) => WorkspaceSettings;
    }): Promise<WorkspaceSettings>;
    static writeCodeWorkspaceSettings({ settings, wsRoot, }: {
        settings: WorkspaceSettings;
        wsRoot: string;
    }): Promise<void>;
    /**
     * Find wsRoot if exists
     * @returns
     */
    static findWSRoot(): string | undefined;
    static findWSRootsInWorkspaceFolders(workspaceFolders: readonly WorkspaceFolderCode[]): Promise<string[]>;
    /**
     * Check if a file is a sail note (vs a regular file or something else entirely)
     */
    static isSailNote({ wsRoot, vaults, fpath, }: {
        fpath: string;
    } & WorkspaceOpts): Promise<boolean>;
    static isNativeWorkspace(workspace: DWorkspaceV2): boolean;
    /**
     * Check if path is in workspace
     * @returns
     */
    static isPathInWorkspace({ wsRoot, vaults, fpath, }: {
        fpath: string;
    } & WorkspaceOpts): boolean;
    /**
     * Return true if contents of note is different from engine
     * @param param0
     * @returns
     */
    static noteContentChanged({ content, note, }: {
        content: string;
        note: NoteProps;
    }): boolean;
    /**
     * Generate url for given note or return `undefined` if no url is specified
     * @param opts
     *
     */
    static getNoteUrl(opts: {
        config: SailConfig;
        note: NoteProps;
        vault: DVault;
        urlRoot?: string;
        anchor?: string;
    }): string;
    /**
     * @param results
     * @returns number of repos that has Sync Action Status done.
     */
    static getCountForStatusDone(results: SyncActionResult[]): number;
    static count(results: SyncActionResult[], status: SyncActionStatus): number;
    /**
     *
     * @param results
     * @param status
     * @returns name of all the repos with status same as @param status.
     */
    static getFilteredRepoNames(results: SyncActionResult[], status: SyncActionStatus): string[];
    static addVaultToWorkspace({ vault, wsRoot, }: {
        vault: DVault;
        wsRoot: string;
    }): Promise<void>;
}
