import { ErrorFactory } from "..";

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

export enum SailEditorViewKey {
  CONFIGURE = "sail.configure",
  NOTE_GRAPH = "sail.graph-note",
  SCHEMA_GRAPH = "sail.graph-schema",
  NOTE_PREVIEW = "sail.note-preview",
  SEED_BROWSER = "sail.seed-browser",
}

export enum SailTreeViewKey {
  SAMPLE_VIEW = "sail.sample",
  TREE_VIEW = "sail.treeView",
  BACKLINKS = "sail.backlinks",
  CALENDAR_VIEW = "sail.calendar-view",
  LOOKUP_VIEW = "sail.lookup-view",
  RECENT_WORKSPACES = "sail.recent-workspaces",
}

export const EDITOR_VIEWS: Record<SailEditorViewKey, SailViewEntry> = {
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
export const TREE_VIEWS: Record<SailTreeViewKey, SailViewEntry> = {
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

export const isWebViewEntry = (
  entry: SailViewEntry
): entry is SailWebViewEntry => {
  return entry.type === "webview";
};

export const getWebTreeViewEntry = (
  key: SailTreeViewKey
): SailWebViewEntry => {
  const out = TREE_VIEWS[key];
  if (isWebViewEntry(out)) {
    return out;
  }
  throw ErrorFactory.createInvalidStateError({
    message: `${key} is not valid webview key`,
  });
};

export const getWebEditorViewEntry = (
  key: SailEditorViewKey
): SailWebViewEntry => {
  const out = EDITOR_VIEWS[key];
  if (isWebViewEntry(out)) {
    return out;
  }
  throw ErrorFactory.createInvalidStateError({
    message: `${key} is not valid webview key`,
  });
};

export enum BacklinkPanelSortOrder {
  /** Using path sorted so order with shallow first = true */
  PathNames = "PathNames",

  LastUpdated = "LastUpdated",
}
