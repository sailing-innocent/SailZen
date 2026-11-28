/* eslint-disable camelcase */
import { ConfigUtils, } from "@saili/common-all";
import _ from "lodash";
class MigrationUtils {
    /**
     * clean up an object recursively with given predicate.
     * @param obj a plain object
     * @param pred predicate to use for recursively omitting
     * @returns obj, with properties omitted by pred
     */
    static deepCleanObjBy(obj, pred) {
        const out = _.omitBy(obj, pred);
        _.keys(out).forEach((key) => {
            if (_.isPlainObject(out[key])) {
                out[key] = MigrationUtils.deepCleanObjBy(out[key], pred);
            }
        });
        return out;
    }
    static getMigrationAnalyticProps({ data: { changeName, status, version }, }) {
        return {
            data: {
                changeName,
                status,
                version,
            },
        };
    }
}
const toBoolean = (value) => value.toString().toLowerCase() === "true";
const DEPRECATED_PATHS = [
    "useNunjucks",
    "noLegacyNoteRef",
    "site.siteNotesDir",
    "site.siteRepoDir",
    "site.previewPort",
    "site.useContainers",
    "site.generateChangelog",
    "dev.enableWebUI",
    "workspace.enableHandlebarTemplates",
    "workspace.enableSmartRefs",
    "preview.enableMermaid",
    "enableMermaid",
    "publishing.enableMermaid",
];
/**
 * Used as an function to map a config that has been flipped during migration.
 * @param value boolean value
 * @returns flipped boolean value
 */
const FLIP = (value) => !value;
export const PATH_MAP = new Map([
    // commands namespace
    // lookup namespace
    ["commands.lookup", { target: "lookup", iteratee: "skip" }],
    // note lookup namespace
    ["commands.lookup.note", { target: "lookup.note", iteratee: "skip" }],
    [
        "commands.lookup.note.selectionMode",
        {
            target: "lookup.note.selectionType",
            iteratee: (value) => {
                switch (value) {
                    case "selection2link": {
                        return "link";
                    }
                    case "none": {
                        return "none";
                    }
                    case "selectionExtract":
                    default: {
                        return "extract";
                    }
                }
            },
        },
    ],
    [
        "commands.lookup.note.confirmVaultOnCreate",
        { target: "lookupConfirmVaultOnCreate" },
    ],
    ["commands.lookup.note.leaveTrace", { target: "lookup.note.leaveTrace" }],
    [
        "commands.lookup.note.bubbleUpCreateNew",
        { target: "lookupDontBubbleUpCreateNew", iteratee: FLIP },
    ],
    // insertNote namespace
    ["commands.insertNote.initialValue", { target: "defaultInsertHierarchy" }],
    // insertNoteLink namepsace
    ["commands.insertNoteLink", { target: "insertNoteLink", iteratee: "skip" }],
    ["commands.insertNoteLink.aliasMode", { target: "insertNoteLink.aliasMode" }],
    [
        "commands.insertNoteLink.enableMultiSelect",
        { target: "insertNoteLink.multiSelect" },
    ],
    // insertNoteIndex namespace
    ["commands.insertNoteIndex", { target: "insertNoteIndex", iteratee: "skip" }],
    [
        "commands.insertNoteIndex.enableMarker",
        { target: "insertNoteIndex.marker" },
    ],
    // randomNote namespace
    ["commands.randomNote", { target: "randomNote", iteratee: "skip" }],
    ["commands.randomNote.include", { target: "randomNote.include" }],
    ["commands.randomNote.exclude", { target: "randomNote.exclude" }],
    // workspace namespace
    ["workspace.sailVersion", { target: "sailVersion" }],
    ["workspace.workspaces", { target: "workspaces" }],
    ["workspace.seeds", { target: "seeds" }],
    ["workspace.vaults", { target: "vaults" }],
    ["workspace.hooks", { target: "hooks" }],
    // journal namespace
    ["workspace.journal", { target: "journal", iteratee: "skip" }],
    ["workspace.journal.dailyDomain", { target: "journal.dailyDomain" }],
    ["workspace.journal.dailyVault", { target: "journal.dailyVault" }],
    ["workspace.journal.name", { target: "journal.name" }],
    ["workspace.journal.dateFormat", { target: "journal.dateFormat" }],
    ["workspace.journal.addBehavior", { target: "journal.addBehavior" }],
    // scratch namespace
    ["workspace.scratch", { target: "scratch", iteratee: "skip" }],
    ["workspace.scratch.name", { target: "scratch.name" }],
    ["workspace.scratch.dateFormat", { target: "scratch.dateFormat" }],
    ["workspace.scratch.addBehavior", { target: "scratch.addBehavior" }],
    // graph namespace
    ["workspace.graph", { target: "graph", iteratee: "skip" }],
    ["workspace.graph.zoomSpeed", { target: "graph.zoomSpeed" }],
    ["workspace.disableTelemetry", { target: "noTelemetry" }],
    [
        "workspace.enableAutoCreateOnDefinition",
        { target: "noAutoCreateOnDefinition", iteratee: FLIP },
    ],
    [
        "workspace.enableXVaultWikiLink",
        { target: "noXVaultWikiLink", iteratee: FLIP },
    ],
    ["workspace.enableRemoteVaultInit", { target: "initializeRemoteVaults" }],
    ["workspace.workspaceVaultSyncMode", { target: "workspaceVaultSync" }],
    ["workspace.enableAutoFoldFrontmatter", { target: "autoFoldFrontmatter" }],
    ["workspace.maxPreviewsCached", { target: "maxPreviewsCached" }],
    ["workspace.maxNoteLength", { target: "maxNoteLength" }],
    ["workspace.feedback", { target: "feedback" }],
    ["workspace.apiEndpoint", { target: "apiEndpoint" }],
    // preview namespace
    ["preview.enableFMTitle", { target: "useFMTitle", preserve: true }],
    [
        "preview.enableHierarchyDisplay",
        { target: "hierarchyDisplay", preserve: true },
    ],
    [
        "preview.hierarchyDisplayTitle",
        { target: "hierarchyDisplayTitle", preserve: true },
    ],
    [
        "preview.enableNoteTitleForLink",
        { target: "useNoteTitleForLink", preserve: true },
    ],
    ["preview.enableMermaid", { target: "mermaid", preserve: true }],
    ["preview.enablePrettyRefs", { target: "usePrettyRefs" }],
    ["preview.enableKatex", { target: "useKatex", preserve: true }],
    // publishing namespace
    ["publishing", { target: "site", iteratee: "skip" }],
    ["publishing.enableFMTitle", { target: "useFMTitle" }],
    ["publishing.enableHierarchyDisplay", { target: "hierarchyDisplay" }],
    ["publishing.hierarchyDisplayTitle", { target: "hierarchyDisplayTitle" }],
    ["publishing.enableNoteTitleForLink", { target: "useNoteTitleForLink" }],
    ["publishing.enableMermaid", { target: "mermaid" }],
    ["publishing.enablePrettyRefs", { target: "site.usePrettyRefs" }],
    ["publishing.enableKatex", { target: "useKatex" }],
    ["publishing.assetsPrefix", { target: "site.assetsPrefix" }],
    ["publishing.copyAssets", { target: "site.copyAssets" }],
    ["publishing.canonicalBaseUrl", { target: "site.canonicalBaseUrl" }],
    ["publishing.customHeaderPath", { target: "site.customHeaderPath" }],
    ["publishing.ga.tracking", { target: "site.ga_tracking" }],
    ["publishing.logoPath", { target: "site.logo" }],
    ["publishing.siteFaviconPath", { target: "site.siteFaviconPath" }],
    ["publishing.siteIndex", { target: "site.siteIndex" }],
    ["publishing.siteHierarchies", { target: "site.siteHierarchies" }],
    ["publishing.enableSiteLastModified", { target: "site.siteLastModified" }],
    ["publishing.siteRootDir", { target: "site.siteRootDir" }],
    ["publishing.siteUrl", { target: "site.siteUrl" }],
    ["publishing.enableFrontmatterTags", { target: "site.showFrontMatterTags" }],
    ["publishing.enableHashesForFMTags", { target: "site.useHashesForFMTags" }],
    [
        "publishing.enableRandomlyColoredTags",
        { target: "site.noRandomlyColoredTags", iteratee: FLIP },
    ],
    [
        "publishing.hierarchy",
        {
            target: "site.config",
            iteratee: (hconfig) => {
                const tmp = {};
                _.forEach(_.keys(hconfig), (key) => {
                    _.set(tmp, key, _.omit(_.get(hconfig, key), "noindexByDefault"));
                });
                return tmp;
            },
        },
    ],
    [
        "publishing.duplicateNoteBehavior",
        { target: "site.duplicateNoteBehavior" },
    ],
    ["publishing.writeStubs", { target: "site.writeStubs" }],
    ["publishing.seo.title", { target: "site.title" }],
    ["publishing.seo.description", { target: "site.description" }],
    ["publishing.seo.author", { target: "site.author" }],
    ["publishing.seo.twitter", { target: "site.twitter" }],
    ["publishing.seo.image", { target: "site.image" }],
    ["publishing.github.cname", { target: "site.githubCname" }],
    [
        "publishing.github.enableEditLink",
        { target: "site.gh_edit_link", iteratee: toBoolean },
    ],
    ["publishing.github.editLinkText", { target: "site.gh_edit_link_text" }],
    ["publishing.github.editBranch", { target: "site.gh_edit_branch" }],
    ["publishing.github.editViewMode", { target: "site.gh_edit_view_mode" }],
    ["publishing.github.editRepository", { target: "site.gh_edit_repository" }],
    ["publishing.segmentKey", { target: "site.segmentKey" }],
    ["publishing.cognitoUserPoolId", { target: "site.cognitoUserPoolId" }],
    ["publishing.cognitoClientId", { target: "site.cognitoClientId" }],
    ["publishing.enablePrettyLinks", { target: "site.usePrettyLinks" }],
]);
var LegacyNoteAddBehavior;
(function (LegacyNoteAddBehavior) {
    LegacyNoteAddBehavior["childOfDomain"] = "childOfDomain";
    LegacyNoteAddBehavior["childOfDomainNamespace"] = "childOfDomainNamespace";
    LegacyNoteAddBehavior["childOfCurrent"] = "childOfCurrent";
    LegacyNoteAddBehavior["asOwnDomain"] = "asOwnDomain";
})(LegacyNoteAddBehavior || (LegacyNoteAddBehavior = {}));
var LegacyLookupSelectionType;
(function (LegacyLookupSelectionType) {
    LegacyLookupSelectionType["selection2link"] = "selection2link";
    LegacyLookupSelectionType["selectionExtract"] = "selectionExtract";
    LegacyLookupSelectionType["none"] = "none";
})(LegacyLookupSelectionType || (LegacyLookupSelectionType = {}));
var LegacyInsertNoteLinkAliasMode;
(function (LegacyInsertNoteLinkAliasMode) {
    LegacyInsertNoteLinkAliasMode["snippet"] = "snippet";
    LegacyInsertNoteLinkAliasMode["selection"] = "selection";
    LegacyInsertNoteLinkAliasMode["title"] = "title";
    LegacyInsertNoteLinkAliasMode["prompt"] = "prompt";
    LegacyInsertNoteLinkAliasMode["none"] = "none";
})(LegacyInsertNoteLinkAliasMode || (LegacyInsertNoteLinkAliasMode = {}));
var LegacyDuplicateNoteAction;
(function (LegacyDuplicateNoteAction) {
    LegacyDuplicateNoteAction["USE_VAULT"] = "useVault";
})(LegacyDuplicateNoteAction || (LegacyDuplicateNoteAction = {}));
// ===
export class DConfigLegacy {
    static configIsV4(config) {
        return config.version === 4;
    }
    static v4ToV5(config) {
        return v4ToV5({ legacyConfig: config });
    }
}
const v4ToV5 = ({ legacyConfig }) => {
    const defaultV5Config = ConfigUtils.genDefaultConfig();
    const rawSailConfig = legacyConfig;
    // remove all null properties
    const cleanSailConfig = MigrationUtils.deepCleanObjBy(rawSailConfig, _.isNull);
    if (_.isUndefined(cleanSailConfig.commands)) {
        cleanSailConfig.commands = {};
    }
    if (_.isUndefined(cleanSailConfig.workspace)) {
        cleanSailConfig.workspace = {};
    }
    if (_.isUndefined(cleanSailConfig.preview)) {
        cleanSailConfig.preview = {};
    }
    if (_.isUndefined(cleanSailConfig.publishing)) {
        cleanSailConfig.publishing = {};
    }
    // legacy paths to remove from config;
    const legacyPaths = [];
    // migrate each path mapped in current config version
    PATH_MAP.forEach((value, key) => {
        const { target: legacyPath, preserve } = value;
        let iteratee = value.iteratee;
        let valueToFill;
        let alreadyFilled;
        if (iteratee !== "skip") {
            alreadyFilled = _.has(cleanSailConfig, key);
            const maybeLegacyConfig = _.get(cleanSailConfig, legacyPath);
            if (_.isUndefined(maybeLegacyConfig)) {
                // legacy property doesn't have a value.
                valueToFill = _.get(defaultV5Config, key);
            }
            else {
                // there is a legacy value.
                // check if this mapping needs special treatment.
                if (_.isUndefined(iteratee)) {
                    // assume identity mapping.
                    iteratee = _.identity;
                }
                valueToFill = iteratee(maybeLegacyConfig);
            }
        }
        if (!alreadyFilled && !_.isUndefined(valueToFill)) {
            // if the property isn't already filled, fill it with determined value.
            _.set(cleanSailConfig, key, valueToFill);
        }
        // these will later be used to delete.
        // only push if we aren't preserving target.
        if (!preserve) {
            legacyPaths.push(legacyPath);
        }
    });
    // set config version.
    _.set(cleanSailConfig, "version", 5);
    // add deprecated paths to legacyPaths
    // so they could be unset if they exist
    legacyPaths.push(...DEPRECATED_PATHS);
    // remove legacy property from config after migration.
    legacyPaths.forEach((legacyPath) => {
        _.unset(cleanSailConfig, legacyPath);
    });
    // recursively populate missing defaults
    const migratedConfig = _.defaultsDeep(cleanSailConfig, defaultV5Config);
    return migratedConfig;
};
//# sourceMappingURL=ConfigCompat.js.map