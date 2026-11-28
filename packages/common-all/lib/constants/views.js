import { ErrorFactory } from "..";
export var SailEditorViewKey;
(function (SailEditorViewKey) {
    SailEditorViewKey["CONFIGURE"] = "sail.configure";
    SailEditorViewKey["NOTE_GRAPH"] = "sail.graph-note";
    SailEditorViewKey["SCHEMA_GRAPH"] = "sail.graph-schema";
    SailEditorViewKey["NOTE_PREVIEW"] = "sail.note-preview";
    SailEditorViewKey["SEED_BROWSER"] = "sail.seed-browser";
})(SailEditorViewKey || (SailEditorViewKey = {}));
export var SailTreeViewKey;
(function (SailTreeViewKey) {
    SailTreeViewKey["SAMPLE_VIEW"] = "sail.sample";
    SailTreeViewKey["TREE_VIEW"] = "sail.treeView";
    SailTreeViewKey["BACKLINKS"] = "sail.backlinks";
    SailTreeViewKey["CALENDAR_VIEW"] = "sail.calendar-view";
    SailTreeViewKey["LOOKUP_VIEW"] = "sail.lookup-view";
    SailTreeViewKey["RECENT_WORKSPACES"] = "sail.recent-workspaces";
})(SailTreeViewKey || (SailTreeViewKey = {}));
export const EDITOR_VIEWS = {
    [SailEditorViewKey.NOTE_PREVIEW]: {
        desc: "Note Preview",
        label: "Note Preview",
        bundleName: "SailNotePreview",
        type: "webview",
    },
    [SailEditorViewKey.CONFIGURE]: {
        desc: "Sail Configuration",
        label: "Sail Configuration",
        bundleName: "SailConfigure",
        type: "webview",
    },
    [SailEditorViewKey.NOTE_GRAPH]: {
        desc: "Note Graph",
        label: "Note Graph",
        bundleName: "SailGraphPanel",
        type: "webview",
    },
    [SailEditorViewKey.SCHEMA_GRAPH]: {
        desc: "Schema Graph",
        label: "Schema Graph",
        bundleName: "SailSchemaGraphPanel",
        type: "webview",
    },
    [SailEditorViewKey.SEED_BROWSER]: {
        desc: "Seed Registry",
        label: "Seed Registry",
        bundleName: "SeedBrowser",
        type: "webview",
    },
};
/**
 * Value is the name of webpack bundle for webview based tree views
 */
export const TREE_VIEWS = {
    [SailTreeViewKey.SAMPLE_VIEW]: {
        desc: "A view used for prototyping",
        label: "Sample View",
        bundleName: "SampleComponent",
        type: "webview",
    },
    [SailTreeViewKey.TREE_VIEW]: {
        desc: "Tree View",
        label: "Tree View",
        type: "nativeview",
    },
    [SailTreeViewKey.BACKLINKS]: {
        desc: "Shows all backlinks to the currentnote",
        label: "Backlinks",
        type: "nativeview",
    },
    [SailTreeViewKey.CALENDAR_VIEW]: {
        desc: "Calendar View",
        label: "Calendar View",
        type: "webview",
        bundleName: "SailCalendarPanel",
    },
    [SailTreeViewKey.LOOKUP_VIEW]: {
        desc: "Lookup View",
        label: "Lookup View",
        type: "webview",
        bundleName: "SailLookupPanel",
    },
    [SailTreeViewKey.RECENT_WORKSPACES]: {
        desc: "Recent Sail Workspaces",
        label: "Recent Sail Workspaces",
        type: "nativeview",
    },
};
export const isWebViewEntry = (entry) => {
    return entry.type === "webview";
};
export const getWebTreeViewEntry = (key) => {
    const out = TREE_VIEWS[key];
    if (isWebViewEntry(out)) {
        return out;
    }
    throw ErrorFactory.createInvalidStateError({
        message: `${key} is not valid webview key`,
    });
};
export const getWebEditorViewEntry = (key) => {
    const out = EDITOR_VIEWS[key];
    if (isWebViewEntry(out)) {
        return out;
    }
    throw ErrorFactory.createInvalidStateError({
        message: `${key} is not valid webview key`,
    });
};
export var BacklinkPanelSortOrder;
(function (BacklinkPanelSortOrder) {
    /** Using path sorted so order with shallow first = true */
    BacklinkPanelSortOrder["PathNames"] = "PathNames";
    BacklinkPanelSortOrder["LastUpdated"] = "LastUpdated";
})(BacklinkPanelSortOrder || (BacklinkPanelSortOrder = {}));
//# sourceMappingURL=views.js.map