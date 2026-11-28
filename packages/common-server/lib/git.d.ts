import { DVault, DWorkspaceLegacy, NoteProps, SailConfig } from "@saili/common-all";
import simpleGit, { SimpleGit, ResetMode as SimpleGitResetMode } from "simple-git";
export { simpleGit, SimpleGit, SimpleGitResetMode };
/**
 *  NOTICE: Lots of the Git code is obtained from https://github.com/KnisterPeter/vscode-github, licened under MIT
 */
/**
 * Utilities for working with git urls
 */
export declare class GitUtils {
    static canShowGitLink(opts: {
        config: SailConfig;
        note: NoteProps;
    }): boolean;
    static getGithubAccessTokenUrl(opts: {
        remotePath: string;
        accessToken: string;
    }): string;
    static git2Github(gitUrl: string): string;
    static getGithubEditUrl(opts: {
        note: NoteProps;
        config: SailConfig;
        wsRoot: string;
    }): string;
    static getOwnerAndRepoFromURL(url: string): {
        owner: string;
        repo: string;
    };
    static getRepoNameFromURL(url: string): string;
    static remoteUrlToDependencyPath({ vaultName, url, }: {
        vaultName: string;
        url?: string;
    }): string;
    static getDependencyPathWithRemote({ vault, remote, }: {
        remote: string | null;
        vault: DVault;
    }): string;
    static getVaultFromRepo(opts: {
        repoPath: string;
        repoUrl: string;
        wsRoot: string;
    }): DVault;
    static getVaultsFromRepo(opts: {
        repoPath: string;
        repoUrl: string;
        wsRoot: string;
    }): Promise<{
        vaults: DVault[];
        workspace?: DWorkspaceLegacy;
    }>;
    static isRepo(src: string): boolean;
    static getGitRoot(uri: string): Promise<string | undefined>;
    static getGithubFileUrl(uri: string, file: string, line?: number, endLine?: number): Promise<string>;
    static getGitHostname(uri: string): Promise<string>;
    /**
     * Looks at URI for git repo
     * @param uri
     * @returns
     */
    static getGitProviderOwnerAndRepositoryFromGitConfig(uri: string): Promise<string[]>;
    static getRemoteName(uri: string): Promise<string>;
    static calculateRemoteName(uri: string): Promise<string | undefined>;
    static parseGitUrl(remote: string): string[];
    static parseGitProviderUrl(remote: string): string[];
    static getGitProviderOwnerAndRepositoryFromHttpUrl(remote: string): string[];
    static getRemoteNames(uri: string): Promise<string[]>;
    static getGitProviderOwnerAndRepository(uri: string): Promise<string[]>;
    static getCurrentBranch(uri: string): Promise<string | undefined>;
    static execute(cmd: string, uri: string): Promise<{
        stdout: string;
        stderr: string;
    }>;
    /** Add a file or folder to the gitignore, avoiding creating exact duplicate lines.
     *
     * Creates the gitignore file if missing.
     *
     * @param addPath The path to add to the gitignore
     * @param root The root folder containing the `.gitignore` file.
     * @param noCreateIfMissing If true, `.gitignore` won't be created if it is missing
     */
    static addToGitignore({ addPath, root, noCreateIfMissing, }: {
        addPath: string;
        root: string;
        noCreateIfMissing?: boolean;
    }): Promise<void>;
    /** Remove a file or folder from the gitignore.
     *
     * Does nothing if the gitignore is missing, or if the file or folder wasn't already in it.
     *
     * @param removePath The path to remove from the gitignore
     * @param root The root folder containing the `.gitignore` file.
     */
    static removeFromGitignore({ removePath, root, }: {
        removePath: string;
        root: string;
    }): Promise<void>;
    /**
     *
     * @param uri
     * @param file
     * @returns codespaces url for the note
     */
    static getCodeSpacesURL(uri: string, file: string): Promise<string>;
}
