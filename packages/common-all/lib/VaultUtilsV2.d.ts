import { URI } from "vscode-uri";
import { DVault } from "./types/DVault";
/**
 * This version is meant to use URI instead of string paths to make it work on
 * all FS environments. It also should not use 'path' to maximize OS
 * compatibility.
 */
export declare class VaultUtilsV2 {
    static getRelPathFragments(vault: DVault): string | string[];
    /**
     * For a given file path, return which vault the file path is a part of, if any.
     * @param param0
     * @returns
     */
    static getVaultByFilePath({ wsRoot, vaults, fsPath, }: {
        wsRoot: URI;
        fsPath: URI;
        vaults: DVault[];
    }): DVault | undefined;
}
