import { FOLDERS, Time, TreeViewItemLabelTypeEnum, } from "@saili/common-all";
import fs from "fs-extra";
import os from "os";
import path from "path";
export var ShowcaseEntry;
(function (ShowcaseEntry) {
    ShowcaseEntry["TryMeetingNotes"] = "TryMeetingNotes";
    ShowcaseEntry["AutocompleteTip"] = "AutocompleteTip";
    ShowcaseEntry["TagsTip"] = "TagsTip";
    ShowcaseEntry["RenameHeader"] = "RenameHeader";
    ShowcaseEntry["TaskManagement"] = "TaskManagement";
    ShowcaseEntry["BlockRefs"] = "BlockRefs";
    ShowcaseEntry["HeaderRefs"] = "HeaderRefs";
    ShowcaseEntry["InsertNoteLink"] = "InsertNoteLink";
    ShowcaseEntry["GraphTheme"] = "GraphTheme";
    ShowcaseEntry["PublishTheme"] = "PublishTheme";
    ShowcaseEntry["PreviewTheme"] = "PreviewTheme";
    ShowcaseEntry["GraphPanel"] = "GraphPanel";
    ShowcaseEntry["BacklinksPanelHover"] = "BacklinksPanelHover";
    ShowcaseEntry["ObsidianImport"] = "ObsidianImport";
    ShowcaseEntry["SettingsUI"] = "SettingsUI";
    ShowcaseEntry["CreateScratchNoteKeybindingTip"] = "CreateScratchNoteKeybindingTip";
})(ShowcaseEntry || (ShowcaseEntry = {}));
/**
 * Survey for users on which prior note-taking tools they've used.
 */
export var PriorTools;
(function (PriorTools) {
    PriorTools["No"] = "No";
    PriorTools["Foam"] = "Foam";
    PriorTools["Roam"] = "Roam";
    PriorTools["Logseq"] = "Logseq";
    PriorTools["Notion"] = "Notion";
    PriorTools["OneNote"] = "OneNote";
    PriorTools["Obsidian"] = "Obsidian";
    PriorTools["Evernote"] = "Evernote";
    PriorTools["GoogleKeep"] = "Google Keep";
    PriorTools["Confluence"] = "Confluence";
    PriorTools["Other"] = "Other";
})(PriorTools || (PriorTools = {}));
export var InactvieUserMsgStatusEnum;
(function (InactvieUserMsgStatusEnum) {
    InactvieUserMsgStatusEnum["submitted"] = "submitted";
    InactvieUserMsgStatusEnum["cancelled"] = "cancelled";
})(InactvieUserMsgStatusEnum || (InactvieUserMsgStatusEnum = {}));
export var InitialSurveyStatusEnum;
(function (InitialSurveyStatusEnum) {
    InitialSurveyStatusEnum["submitted"] = "submitted";
    InitialSurveyStatusEnum["cancelled"] = "cancelled";
})(InitialSurveyStatusEnum || (InitialSurveyStatusEnum = {}));
export var LapsedUserSurveyStatusEnum;
(function (LapsedUserSurveyStatusEnum) {
    LapsedUserSurveyStatusEnum["submitted"] = "submitted";
    LapsedUserSurveyStatusEnum["cancelled"] = "cancelled";
})(LapsedUserSurveyStatusEnum || (LapsedUserSurveyStatusEnum = {}));
export var WorkspaceActivationContext;
(function (WorkspaceActivationContext) {
    // UNSET - Indicates this is the first Workspace Launch
    WorkspaceActivationContext[WorkspaceActivationContext["normal"] = 0] = "normal";
    WorkspaceActivationContext[WorkspaceActivationContext["tutorial"] = 1] = "tutorial";
    WorkspaceActivationContext[WorkspaceActivationContext["seedBrowser"] = 2] = "seedBrowser";
})(WorkspaceActivationContext || (WorkspaceActivationContext = {}));
let _singleton;
export class MetadataService {
    static instance() {
        if (!_singleton) {
            _singleton = new MetadataService();
        }
        return _singleton;
    }
    static metaFilePath() {
        return path.join(os.homedir(), FOLDERS.SAIL_SYSTEM_ROOT, "meta.json");
    }
    deleteMeta(key) {
        const stateFromFile = this.getMeta();
        delete stateFromFile[key];
        fs.writeJSONSync(MetadataService.metaFilePath(), stateFromFile, {
            spaces: 4,
        });
    }
    getMeta() {
        const metaPath = MetadataService.metaFilePath();
        if (!fs.pathExistsSync(metaPath)) {
            fs.ensureFileSync(metaPath);
            fs.writeJSONSync(metaPath, {});
            return {};
        }
        return fs.readJSONSync(MetadataService.metaFilePath());
    }
    getFeatureShowcaseStatus(key) {
        const featureShowcaseData = this.getMeta().featureShowcase;
        if (!featureShowcaseData) {
            return undefined;
        }
        return featureShowcaseData[key];
    }
    getGlobalVersion() {
        return this.getMeta().version || "0.0.0";
    }
    getLapsedUserSurveyStatus() {
        return this.getMeta().lapsedUserSurveyStatus;
    }
    getActivationContext() {
        return (this.getMeta().workspaceActivationContext ??
            WorkspaceActivationContext.normal);
    }
    getGraphTheme() {
        return this.getMeta().graphTheme;
    }
    getTreeViewItemLabelType() {
        return (this.getMeta().treeViewItemLabelType || TreeViewItemLabelTypeEnum.title);
    }
    get BacklinksPanelSortOrder() {
        return this.getMeta().backlinksPanelSortOrder;
    }
    get priorTools() {
        return this.getMeta().priorTools;
    }
    get RecentWorkspaces() {
        return this.getMeta().recentWorkspaces;
    }
    get graphDepth() {
        return this.getMeta().graphDepth;
    }
    setMeta(key, value) {
        const stateFromFile = this.getMeta();
        stateFromFile[key] = value;
        fs.writeJSONSync(MetadataService.metaFilePath(), stateFromFile, {
            spaces: 4,
        });
    }
    get v100ReleaseMessageShown() {
        return this.getMeta().v100ReleaseMessageShown;
    }
    get firstInstallVersion() {
        return this.getMeta().firstInstallVersion;
    }
    /**
     * Set first install logic
     *  ^o4y7ijuvi5nv
     */
    setInitialInstall(time) {
        time ||= Time.now().toSeconds();
        this.setMeta("firstInstall", time);
    }
    setInitialInstallVersion(version) {
        this.setMeta("firstInstallVersion", version);
    }
    setFirstWsInitialize() {
        this.setMeta("firstWsInitialize", Time.now().toSeconds());
    }
    setLapsedUserMsgSendTime() {
        this.setMeta("lapsedUserMsgSendTime", Time.now().toSeconds());
    }
    setSailWorkspaceActivated() {
        this.setMeta("sailWorkspaceActivated", Time.now().toSeconds());
    }
    setFirstLookupTime() {
        this.setMeta("firstLookupTime", Time.now().toSeconds());
    }
    setLastLookupTime() {
        this.setMeta("lastLookupTime", Time.now().toSeconds());
    }
    setInactiveUserMsgSendTime() {
        this.setMeta("inactiveUserMsgSendTime", Time.now().toSeconds());
    }
    setInactiveUserMsgStatus(value) {
        this.setMeta("inactiveUserMsgStatus", value);
    }
    setInitialSurveyStatus(value) {
        this.setMeta("initialSurveyStatus", value);
    }
    setLapsedUserSurveyStatus(value) {
        this.setMeta("lapsedUserSurveyStatus", value);
    }
    setGlobalVersion(value) {
        this.setMeta("version", value);
    }
    setFeatureShowcaseStatus(key) {
        const meta = this.getMeta();
        if (!meta.featureShowcase) {
            meta.featureShowcase = {};
        }
        meta.featureShowcase[key] = Time.now().toSeconds();
        return this.setMeta("featureShowcase", meta.featureShowcase);
    }
    setActivationContext(context) {
        this.setMeta("workspaceActivationContext", context);
    }
    setGraphTheme(graphTheme) {
        const meta = this.getMeta();
        if (meta.graphTheme !== graphTheme) {
            this.setMeta("graphTheme", graphTheme);
        }
    }
    set graphDepth(graphDepth) {
        const meta = this.getMeta();
        if (meta.graphDepth !== graphDepth) {
            this.setMeta("graphDepth", graphDepth);
        }
    }
    setTreeViewItemLabelType(labelType) {
        this.setMeta("treeViewItemLabelType", labelType);
    }
    set BacklinksPanelSortOrder(sortOrder) {
        this.setMeta("backlinksPanelSortOrder", sortOrder);
    }
    setFirstDailyJournalTime() {
        this.setMeta("firstDailyJournalTime", Time.now().toSeconds());
    }
    set priorTools(priorTools) {
        this.setMeta("priorTools", priorTools);
    }
    set v100ReleaseMessageShown(hasShown) {
        this.setMeta("v100ReleaseMessageShown", hasShown);
    }
    // Add a single path to recent workspaces. Recent workspaces acts like a FIFO
    // queue
    addToRecentWorkspaces(path) {
        const RECENT_WORKSPACE_ITEM_LIMIT = 5;
        const current = this.getMeta().recentWorkspaces;
        const updated = [];
        if (!current) {
            updated.push(path);
        }
        else {
            current.forEach((existingPath) => {
                if (existingPath !== path) {
                    updated.push(existingPath);
                }
            });
            if (updated.length >= RECENT_WORKSPACE_ITEM_LIMIT) {
                updated.pop();
            }
            // The first element of the array is the most recent
            updated.unshift(path);
        }
        this.setMeta("recentWorkspaces", updated);
    }
}
//# sourceMappingURL=service.js.map