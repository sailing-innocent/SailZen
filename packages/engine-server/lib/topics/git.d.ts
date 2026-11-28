/**
 * Work directly with git repositories
 */
export declare class Git {
    opts: {
        localUrl: string;
        remoteUrl?: string;
        bare?: boolean;
    };
    static getRepo(fpath: string): Promise<any | false>;
    constructor(opts: {
        localUrl: string;
        remoteUrl?: string;
        bare?: boolean;
    });
    _execute(cmd: string): Promise<import("execa").Result<{
        cwd: string;
    }>>;
    isRepo(): Promise<boolean>;
    client(gitArgs: string[]): Promise<string>;
    commit(opts: {
        msg: string;
    }): Promise<void>;
    add(args: string): Promise<void>;
    clone(destOverride?: string): Promise<string>;
    /** Adds the `remoteUrl` set in the constructor as a remote. */
    remoteAdd(): Promise<string>;
    remoteSet(remoteName: string): Promise<void>;
    remoteGet(remoteName: string): Promise<string>;
    init(): Promise<void>;
    /** Equivalent to `git branch`.
     *
     * @param opts.m Can be used to rename a branch. If `opts.m.oldBranch` is not provided, it's the current branch.
     */
    branch(opts: {
        m?: {
            oldBranch?: string;
            newBranch: string;
        };
    }): Promise<void>;
    /** Set the upstream (remote tracking) branch of `branch`.
     *
     * @param opts.branch The branch to configure, defaults to current branch.
     * @param opts.origin The remote that will be set as upstream.
     * @param opts.upstreamBranch The remote branch in `origin` that will be the upstream branch.
     */
    setUpsteamTo(opts: {
        branch?: string;
        origin: string;
        upsteamBranch: string;
    }): Promise<void>;
    pull(): Promise<void>;
    rebaseAbort(): Promise<void>;
    fetch(): Promise<import("execa").Result<{
        cwd: string;
    }>>;
    push(setUpstream?: {
        remote: string;
        branch: string;
    }): Promise<void>;
    /** Creates a dangling stash commit without changing the index or working tree. */
    stashCreate(): Promise<string>;
    /** Confirms that the commit given (output of {@link Git.stashCreate}) is a valid commit. */
    isValidStashCommit(commit: string): Promise<boolean>;
    /** Applies a stash commit created by {@link Git.stashCreate}.
     *
     * @returns true if the stash applied cleanly, false if there was a merge conflict.
     *  False doesn't mean the stash wasn't applied, just that it conflicted.
     */
    stashApplyCommit(commit: string): Promise<boolean>;
    /** Same as `git reset`. If a parameter is passed, it's `git reset --soft` or `git reset --hard`. */
    reset(resetType?: "soft" | "hard"): Promise<void>;
    addAll(): Promise<void>;
    getCommitUpTo(commit?: string): Promise<string[]>;
    getCurrentBranch(): Promise<string>;
    hasChanges(opts?: {
        untrackedFiles?: "all" | "no" | "normal";
    }): Promise<boolean>;
    /** Check that local has changes that upstream doesn't. */
    hasPushableChanges(upstream: string): Promise<boolean>;
    /** These are the short status symbols git uses to identify files with merge conflicts.
     *
     * See the [git docs](https://www.git-scm.com/docs/git-status#_short_format) for details.
     * The symbol pairs marked "unmerged" are the states that can happen when there is a merge conflict.
     */
    private static MERGE_CONFLICT_REGEX;
    /** Returns true if there are merge conflicts, caused by a merge or rebase. */
    hasMergeConflicts(): Promise<boolean>;
    hasAccessToRemote(): Promise<boolean>;
    /** Gets the path of a file inside of the `.git` folder. */
    private getWorkTreePath;
    /** If there's a rebase in progress, returns what type of rebase that is. Otherwise returns `null` if a rebase is **not** in progress.
     *
     * See relevant [git code](https://github.com/git/git/blob/b23dac905bde28da47543484320db16312c87551/wt-status.c#L1666) for which files to check.
     * Thanks to [this amazing answer](https://stackoverflow.com/a/67245016) on StackOverflow.
     *
     * @returns one of the following:
     * - `null` if there is no rebase in progress.
     * - `"interactive"` if there's an interactive rebase (`git rebase --interactive`) in progress.
     * - `"am"` if there's a "mailbox rebase" in progress.
     * - `"regular"` if the 2 special rebase types don't apply, but there is a rebase in progress.
     */
    typeOfRebaseInProgress(): Promise<"regular" | "interactive" | "am" | null>;
    hasRebaseInProgress(): Promise<boolean>;
    hasRemote(): Promise<boolean>;
    /** Checks if a push to remote would succeed by checking if the upstream contains commits that the local branch doesn't.  */
    hasPushableRemote(): Promise<boolean>;
    /** Gets the upstream `origin/branch` the current branch is set up to push to, or `undefined` if it is not set up to push anywhere. */
    getUpstream(): Promise<string | undefined>;
    /** Returns the first remote that has been configured. */
    getRemote(): Promise<string | undefined>;
    /** Returns the URL for the current remote. */
    getRemoteUrl(): Promise<string | undefined>;
    /** Returns the number of contributors to this repository, or undefined if this is not a repository. */
    getNumContributors(): Promise<number | undefined>;
    /**
     * @param nameOnly: If true, only return the file names. Otherwise the full diff including contents is returned.
     * @param oldCommit: The old identifier (e.g. commit, tag, branch) that we are diffing against.
     * @param newCommit: The new identifier (e.g. commit, tag, branch) that we are diffing from.
     */
    diff({ nameOnly, oldCommit, newCommit, }: {
        nameOnly?: boolean;
        oldCommit: string;
        newCommit: string;
    } | {
        nameOnly?: boolean;
        oldCommit: undefined;
        newCommit: undefined;
    }): Promise<string>;
    rm(opts: {
        cached?: boolean;
        recursive?: boolean;
        force?: boolean;
        dryRun?: boolean;
        path: string;
    }): Promise<import("execa").Result<{
        cwd: string;
    }>>;
}
