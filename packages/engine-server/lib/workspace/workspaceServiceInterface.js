export var SyncActionStatus;
(function (SyncActionStatus) {
    SyncActionStatus["DONE"] = "";
    SyncActionStatus["NO_CHANGES"] = "it has no changes";
    SyncActionStatus["NO_REMOTE"] = "it has no remote";
    SyncActionStatus["BAD_REMOTE"] = "can't connect to the remote";
    SyncActionStatus["NO_UPSTREAM"] = "the current branch has no upstream";
    SyncActionStatus["SKIP_CONFIG"] = "it is configured so";
    SyncActionStatus["NOT_PERMITTED"] = "user is not permitted to push to one or more vaults";
    SyncActionStatus["NEW"] = "newly clond repository";
    SyncActionStatus["CANT_STASH"] = "failed to stash changes in working directory";
    SyncActionStatus["MERGE_CONFLICT"] = "has a merge conflict that needs to be resolved";
    SyncActionStatus["MERGE_CONFLICT_LOSES_CHANGES"] = "pulling would cause a merge conflict that would lose local changes";
    SyncActionStatus["MERGE_CONFLICT_AFTER_PULL"] = "a merge conflict happened after the pull";
    SyncActionStatus["MERGE_CONFLICT_AFTER_RESTORE"] = "a merge conflict happened after restoring local changes";
    SyncActionStatus["REBASE_IN_PROGRESS"] = "there's a rebase in progress";
    SyncActionStatus["UNPULLED_CHANGES"] = "there are changes upstream that don't exist locally";
    SyncActionStatus["ERROR"] = "error while syncing";
})(SyncActionStatus || (SyncActionStatus = {}));
//# sourceMappingURL=workspaceServiceInterface.js.map