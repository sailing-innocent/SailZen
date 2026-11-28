import { WorkspaceFolderRaw } from "./types";
import { DVault } from "./types/DVault";
import { NonOptional } from "./utils";
export type SelfContainedVault = Omit<DVault, "selfContained"> & {
    selfContained: true;
};
export type SeedVault = NonOptional<DVault, "seed">;
export declare class VaultUtils {
    static getName(vault: DVault): string;
    static isEqual(vaultSrc: DVault | string, vaultCmp: DVault | string, wsRoot: string): boolean;
    static isEqualV2(vaultSrc: DVault, vaultCmp: DVault): boolean;
    static isSelfContained(vault: DVault): vault is SelfContainedVault;
    static isSeed(vault: DVault): vault is SeedVault;
    static isRemote(vault: DVault): boolean;
    /**
     * Path for the location of notes in this vault, relative to the workspace
     * root.
     *
     * While for old vaults this is the same as
     * {@link VaultUtils.getRelVaultRootPath}, for self contained vaults the notes
     * are located inside the vault in the `notes` subdirectory.
     *
     * @param vault
     * @returns path for location of the notes in the vault, relative to the
     * workspace root
     */
    static getRelPath(vault: DVault): string;
    /**
     * Path for the location of vault root, relative to the workspace root.
     *
     * While for old vaults this is the same as {@link VaultUtils.getRelPath}, for
     * self contained vaults the notes are located inside the vault in the `notes`
     * subdirectory.
     *
     * @param vault
     * @returns path for root of the vault, relative to the workspace root. May be "." for the top level self contained vault.
     */
    static getRelVaultRootPath(vault: DVault): string;
    static getVaultByName({ vaults, vname, }: {
        vname: string;
        vaults: DVault[];
    }): DVault | undefined;
    /**
     * Like {@link getVaultByName} except throw error if undefined
     * @param param0
     * @returns
     */
    static getVaultByNameOrThrow({ vaults, vname, }: {
        vname: string;
        vaults: DVault[];
    }): DVault;
    /**
     * See if a dir path matches that of an existing vault
     * @param param0
     * @returns
     */
    static getVaultByDirPath({ vaults, wsRoot, fsPath, }: {
        /**
         * Absolute or relative path to note
         */
        fsPath: string;
        wsRoot: string;
        vaults: DVault[];
    }): DVault;
    static getVaultByFilePath({ vaults, wsRoot, fsPath, }: {
        /**
         * Absolute or relative path to note
         */
        fsPath: string;
        wsRoot: string;
        vaults: DVault[];
    }): DVault;
    /**
     * Match vault to vaults
     */
    static matchVault: (opts: {
        vault: DVault;
        vaults: DVault[];
        wsRoot: string;
    }) => false | DVault;
    /**
     * Match vault without using wsRoot
     * @param opts
     * @returns
     */
    static matchVaultV2: (opts: {
        vault: DVault;
        vaults: DVault[];
    }) => false | DVault;
    /**
     * Vault path relative to root
     */
    static normVaultPath: (opts: {
        vault: DVault;
        wsRoot: string;
    }) => string;
    /**
     * Get relative path to vault
     * @param opts
     * @returns
     */
    static normPathByWsRoot: (opts: {
        fsPath: string;
        wsRoot: string;
    }) => string;
    static toURIPrefix(vault: DVault): string;
    static toWorkspaceFolder(vault: DVault): WorkspaceFolderRaw;
    static FILE_VAULT_PREFIX: string;
    /** Creates a dummy vault for files that are not in Sail workspace, for example a markdown file that's not in any vault. Do not use for notes. */
    static createForFile({ filePath, wsRoot, }: {
        filePath: string;
        wsRoot: string;
    }): DVault;
    /** Returns true if the vault was created with {@link VaultUtils.createForFile} */
    static isFileVault(vault: DVault): boolean;
}
