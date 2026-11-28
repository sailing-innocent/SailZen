import type { DVault, SailConfig, NoteProps } from "./types";
/**
 *  NOTICE: Lots of the Git code is obtained from https://github.com/KnisterPeter/vscode-github, licened under MIT
 */
/**
 * Utilities for working with git urls
 */
export declare function canShowGitLink(opts: {
    config: SailConfig;
    note: NoteProps;
}): boolean;
export declare function githubUrl(opts: {
    note: NoteProps;
    config: SailConfig;
}): string;
export declare function getGithubEditUrl(opts: {
    note: NoteProps;
    config: SailConfig;
    wsRoot?: string;
}): string;
export declare function git2Github(gitUrl: string): string;
/**
 * Convert a github repo orul to access token format
 */
export declare function getGithubAccessTokenUrl(opts: {
    remotePath: string;
    accessToken: string;
}): string;
export declare function getOwnerAndRepoFromURL(url: string): {
    owner: string;
    repo: string;
};
export declare function getRepoNameFromURL(url: string): string;
/** Find the dependency path for a vault given the remote url. You can use
 * this even if the vault has no remote.
 *
 * This is the relative path within the dependencies folder, like
 * `github.com/sailhq/sail-site`. For more details see the
 * [[Self Contained Vaults RFC|sail://sail.docs/rfc.42-self-contained-vaults]]
 */
export declare function remoteUrlToDependencyPath({ vaultName, url, }: {
    vaultName: string;
    url?: string;
}): string;
/** If this vault had this remote, what path should it be stored under?
 *
 * If the remote is null, then you'll get the path should be if the vault was a local vault.
 */
export declare function getDependencyPathWithRemote({ vault, remote, }: {
    remote: string | null;
    vault: DVault;
}): string;
export declare function getVaultFromRepo(opts: {
    repoPath: string;
    repoUrl: string;
    wsRoot: string;
}): DVault;
