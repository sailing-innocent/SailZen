import { SailConfig, DEngineClient, Disposable, DUser, DVault, DVaultSync, DWorkspaceLegacy, DWorkspaceEntry, InstallStatus, SelfContainedVault, WorkspaceSettings } from "@saili/common-all";
import { DLogger } from "@saili/common-server";
import { MigrationChangeSetStatus } from "../migrations";
import { SeedService } from "../seed";
import { WSMeta } from "../types";
import { IWorkspaceService, SyncActionResult } from "./workspaceServiceInterface";
export type PathExistBehavior = "delete" | "abort" | "continue";
export type WorkspaceServiceCreateOpts = {
    wsRoot: string;
    /**
     * Does workspace come with a vault?
     * - for self contained vault, this is the `notes` folder
     * - for non-self contained vault, this is whatever the user passes in
     */
    wsVault?: DVault;
    /**
     * Additional vaults to create
     */
    additionalVaults?: DVault[];
    /**
     * create sail.code-workspace file
     */
    createCodeWorkspace?: boolean;
    /** Create a self contained vault as the workspace */
    useSelfContainedVault?: boolean;
};
export type WorkspaceServiceOpts = {
    wsRoot: string;
    seedService?: SeedService;
};
type UrlTransformerFunc = (url: string) => string;
type AddRemoveCommonOpts = {
    /**
     * Default: true
     */
    updateConfig?: boolean;
    /**
     * Default: false
     */
    updateWorkspace?: boolean;
    /**
     * Method to run immediately before updating the workspace file - this is
     * useful as updating the workspace file while it's open will sometimes cause
     * the window to reload and the plugin to restart
     */
    onUpdatingWorkspace?: () => Promise<void>;
    /**
     * Method to run immediately after updating the workspace file
     */
    onUpdatedWorkspace?: () => Promise<void>;
};
/** You **must** dispose workspace services you create, otherwise you risk leaking file descriptors which may lead to crashes. */
export declare class WorkspaceService implements Disposable, IWorkspaceService {
    logger: DLogger;
    private loggerDispose;
    protected _seedService: SeedService;
    static isNewVersionGreater({ oldVersion, newVersion, }: {
        oldVersion: string;
        newVersion: string;
    }): boolean;
    static isWorkspaceVault(fpath: string): Promise<boolean>;
    wsRoot: string;
    /** Reminder: you **must** dispose workspace services you create, otherwise you risk leaking file descriptors which may lead to crashes. */
    constructor({ wsRoot, seedService }: WorkspaceServiceOpts);
    dispose(): void;
    get user(): DUser;
    /**
     * @deprecated: not applicable for self cotnained vaults
     */
    static getOrCreateConfig(wsRoot: string): SailConfig;
    get config(): SailConfig;
    get seedService(): SeedService;
    get vaults(): DVault[];
    setConfig(config: SailConfig): Promise<void>;
    setCodeWorkspaceSettingsSync(config: WorkspaceSettings): void;
    getCodeWorkspaceSettingsSync(): WorkspaceSettings | undefined;
    /**
     *
     * @param param0
     * @returns `{vaults}` that have been added
     */
    addWorkspace({ workspace }: {
        workspace: DWorkspaceLegacy;
    }): Promise<{
        vaults: DVault[];
    }>;
    /**
     *
     *
     * @param opts.vault - {@link DVault} to add to workspace
     * @param opts.config - if passed it, make modifications on passed in config instead of {wsRoot}/sail.yml
     * @param opts.updateConfig - default: true, add to sail.yml
     * @param opts.updateWorkspace - default: false, add to sail.code-workspace. Make sure to keep false for Native workspaces.
     * @returns
     */
    addVault(opts: {
        vault: DVault;
        config?: SailConfig;
    } & AddRemoveCommonOpts): Promise<DVault>;
    /**
     * Create vault files if it does not exist
     * @param opts.noAddToConfig: don't add to sail.yml
     * @param opts.addToCodeWorkspace: add to sail.code-workspace
     * @returns void
     *
     * Effects:
     *   - updates `sail.yml` if `noAddToConfig` is not set
     *   - create directory
     *   - create root note and root schema
     */
    createVault(opts: {
        noAddToConfig?: boolean;
        addToCodeWorkspace?: boolean;
    } & Parameters<WorkspaceService["addVault"]>[0]): Promise<DVault>;
    /** Creates the given vault.
     *
     * @param vault Must be a self contained vault. Use
     * {@link VaultUtils.selfContained} to ensure this is correct, which will
     * allow the type to match.
     * @param addToConfig If true, the created vault will be added to the config
     * for the current workspace.
     * @param addToCodeWorkspace If true, the created vault will be added to the
     * `code-workspace` file for the current workspace.
     * @param newVault If true, the root note and schema files, and workspace
     * files will be created inside the vault.
     */
    createSelfContainedVault(opts: {
        addToConfig?: boolean;
        addToCodeWorkspace?: boolean;
        vault: SelfContainedVault;
        newVault: boolean;
    }): Promise<SelfContainedVault>;
    migrateVaultToSelfContained({ vault }: {
        vault: DVault;
    }): Promise<SelfContainedVault>;
    markVaultAsRemoteInConfig(targetVault: DVault, remoteUrl: string): Promise<void>;
    /** Converts a local vault to a remote vault, with `remoteUrl` as the upstream URL. */
    convertVaultRemote({ wsRoot, vault: targetVault, remoteUrl, }: {
        wsRoot: string;
        vault: DVault;
        remoteUrl: string;
    }): Promise<{
        remote: string;
        branch: string;
    }>;
    /** Converts a remote vault to a local vault.
     *
     * If self contained vaults are enabled in the config, it will also move the
     * vault folder to `dependencies/localhost/`. It will not convert the vault
     * into a self contained vault however.
     */
    convertVaultLocal({ wsRoot, vault: targetVault, }: {
        wsRoot: string;
        vault: DVault;
    }): Promise<void>;
    /** For vaults in the same repository, ensure that their sync configurations do not conflict. Returns the coordinated sync config. */
    verifyVaultSyncConfigs(vaults: DVault[]): DVaultSync | undefined;
    /** Checks if a given git command should be used on the vault based on user configuration.
     *
     * @param command The git command that we want to perform.
     * @param repo The location of the repository containing the vaults.
     * @param vaults The vaults on which the operation is being performed on.
     * @returns true if the command can be performed, false otherwise.
     */
    shouldVaultsSync(command: "commit" | "push" | "pull", [root, vaults]: [string, DVault[]]): Promise<boolean>;
    private static generateCommitMessage;
    getAllReposNumContributors(): Promise<number[]>;
    /**
     * Try to get the url of the top level repository.
     * If self contained vault, workspace root should be the top level if remotely tracked.
     * If not self contained, workspace root should be the top level if remotely tracked.
     * If not self contained vault, and workspace root doesn't have a remote url,
     *   This means nothing is remotely tracked, or some vaults in the workspace is tracked, not the workspace itself.
     *   In this case, it is ambiguous what the top level is, and we assume the top level is not tracked remotely.
     * @returns remote url or undefined
     */
    getTopLevelRemoteUrl(): Promise<string | undefined>;
    commitAndAddAll({ engine, }: {
        engine: DEngineClient;
    }): Promise<SyncActionResult[]>;
    /**
     * Initialize all remote vaults
     * @param opts
     * @returns
     */
    initialize(opts?: {
        onSyncVaultsProgress: any;
        onSyncVaultsEnd: any;
    }): Promise<boolean>;
    /**
     * Remove vaults. Currently doesn't delete any files.
     * @param param0
     */
    removeVault(opts: {
        vault: DVault;
    } & AddRemoveCommonOpts): Promise<void>;
    createConfig(): SailConfig;
    static createGitIgnore(wsRoot: string): Promise<void>;
    /**
     * Initialize workspace with specified vaults
     * Files and folders created:
     * wsRoot/
     * - .gitignore
     * - sail.yml
     * - {vaults}/
     *   - root.md
     *   - root.schema.yml
     *
     * NOTE: sail.yml only gets created if you are adding a workspace...
     * @param opts
     */
    static createWorkspace(opts: WorkspaceServiceCreateOpts): Promise<WorkspaceService>;
    static createStandardWorkspace(opts: WorkspaceServiceCreateOpts): Promise<WorkspaceService>;
    /** Given a standard vault, convert it into a self contained vault.
     *
     * The function **mutates** (modifies) the vault object. */
    static standardToSelfContainedVault(vault: DVault): SelfContainedVault;
    /** Creates a new workspace where the workspace is a self contained vault.
     *
     * If the vaults passed to this function are not self contained vaults, they
     * will be converted to self contained vaults before being created. The vault
     * objects passed in are **mutated**.
     *
     * Further, the first vault given will be the self contained vault that is
     * used as the workspace root.
     */
    static createSelfContainedVaultWorkspace(opts: WorkspaceServiceCreateOpts): Promise<WorkspaceService>;
    static createFromConfig(opts: {
        wsRoot: string;
    }): Promise<void>;
    addVaultToCodeWorkspace(vault: DVault): Promise<void>;
    /**
     * Used in createFromConfig
     */
    cloneVaultWithAccessToken(opts: {
        vault: DVault;
    }): Promise<void>;
    /**
     * Clone a vault from a remote source
     * @param opts.vault vaults field
     * @param opts.urlTransformer modify the git url
     */
    cloneVault(opts: {
        vault: DVault;
        urlTransformer?: UrlTransformerFunc;
    }): Promise<string>;
    cloneWorkspace(opts: {
        wsName: string;
        workspace: DWorkspaceEntry;
        wsRoot: string;
        urlTransformer?: UrlTransformerFunc;
    }): Promise<string>;
    getVaultRepo(vault: DVault): Promise<string | undefined>;
    getAllReposVaults(): Promise<Map<string, DVault[]>>;
    getAllRepos(): Promise<string[]>;
    pullVault(opts: {
        vault: DVault;
    }): Promise<string>;
    /** Returns the list of vaults that were attempted to be pulled, even if there was nothing to pull. */
    pullVaults(): Promise<SyncActionResult[]>;
    /** Returns the list of vaults that were attempted to be pushed, even if there was nothing to push. */
    pushVaults(): Promise<SyncActionResult[]>;
    /**
     * Remove all vault caches in workspace
     */
    removeVaultCaches(): Promise<void>;
    /**
     * See if there's anythign we need to change with the configuration
     */
    runMigrationsIfNecessary({ forceUpgrade, workspaceInstallStatus, currentVersion, previousVersion, sailConfig, wsConfig, }: {
        forceUpgrade?: boolean;
        workspaceInstallStatus: InstallStatus;
        currentVersion: string;
        previousVersion: string;
        sailConfig: SailConfig;
        wsConfig?: WorkspaceSettings;
    }): Promise<MigrationChangeSetStatus[]>;
    /**
     * Make sure all vaults are present on file system
     * @param fetchAndPull for repositories that exist, should we also do a fetch? default: false
     * @param skipPrivate skip cloning and pulling of private vaults. default: false
     */
    syncVaults(opts: {
        config: SailConfig;
        progressIndicator?: () => void;
        urlTransformer?: UrlTransformerFunc;
        fetchAndPull?: boolean;
        skipPrivate?: boolean;
    }): Promise<{
        didClone: boolean;
    }>;
    writePort(port: number): void;
    getMeta(): WSMeta;
    writeMeta(opts: {
        version: string;
    }): void;
}
export {};
