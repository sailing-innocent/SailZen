export type SailWebViewEntry = {
    label: string;
    desc: string;
    bundleName: string;
    type: "webview";
};
export type SailNativeViewEntry = {
    label: string;
    desc: string;
    type: "nativeview";
};
export type SailViewEntry = SailWebViewEntry | SailNativeViewEntry;
export declare enum SailEditorViewKey {
    CONFIGURE = "sail.configure",
    NOTE_GRAPH = "sail.graph-note",
    SCHEMA_GRAPH = "sail.graph-schema",
    NOTE_PREVIEW = "sail.note-preview",
    SEED_BROWSER = "sail.seed-browser"
}
export declare enum SailTreeViewKey {
    SAMPLE_VIEW = "sail.sample",
    TREE_VIEW = "sail.treeView",
    BACKLINKS = "sail.backlinks",
    CALENDAR_VIEW = "sail.calendar-view",
    LOOKUP_VIEW = "sail.lookup-view",
    RECENT_WORKSPACES = "sail.recent-workspaces"
}
export declare const EDITOR_VIEWS: Record<SailEditorViewKey, SailViewEntry>;
/**
 * Value is the name of webpack bundle for webview based tree views
 */
export declare const TREE_VIEWS: Record<SailTreeViewKey, SailViewEntry>;
export declare const isWebViewEntry: (entry: SailViewEntry) => entry is SailWebViewEntry;
export declare const getWebTreeViewEntry: (key: SailTreeViewKey) => SailWebViewEntry;
export declare const getWebEditorViewEntry: (key: SailEditorViewKey) => SailWebViewEntry;
export declare enum BacklinkPanelSortOrder {
    /** Using path sorted so order with shallow first = true */
    PathNames = "PathNames",
    LastUpdated = "LastUpdated"
}
