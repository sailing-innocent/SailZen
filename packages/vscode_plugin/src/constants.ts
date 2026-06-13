import {
  BacklinkPanelSortOrder,
  SailTreeViewKey,
  DENDRON_VSCODE_CONFIG_KEYS,
  isWebViewEntry,
  TreeViewItemLabelTypeEnum,
  TREE_VIEWS,
} from "@saili/common-all";
import { CodeConfigKeys } from "./types";

export const extensionQualifiedId = `sail.sail`;
export const DEFAULT_LEGACY_VAULT_NAME = "vault";

export enum SailContext {
  PLUGIN_ACTIVE = "sail:pluginActive",
  PLUGIN_NOT_ACTIVE = "!sail:pluginActive",
  DEV_MODE = "sail:devMode",
  HAS_LEGACY_PREVIEW = "sail:hasLegacyPreview",
  HAS_CUSTOM_MARKDOWN_VIEW = "hasCustomMarkdownPreview",
  NOTE_LOOK_UP_ACTIVE = "sail:noteLookupActive",
  SHOULD_SHOW_LOOKUP_VIEW = "sail:shouldShowLookupView",
  BACKLINKS_SORT_ORDER = "sail:backlinksSortOrder",
  TREEVIEW_TREE_ITEM_LABEL_TYPE = "sail:treeviewItemLabelType",
}

const treeViewConfig2VSCodeEntry = (id: SailTreeViewKey) => {
  const entry = TREE_VIEWS[id];
  const out: {
    id: string;
    name: string;
    type?: "webview";
  } = {
    id,
    name: entry.label,
  };
  if (isWebViewEntry(entry)) {
    out.type = "webview";
  }
  return out;
};

/**
 * Invocation point for the LaunchTutorialCommand. Used for telemetry purposes
 */
export enum LaunchTutorialCommandInvocationPoint {
  RecentWorkspacesPanel = "RecentWorkspacesPanel",
  WelcomeWebview = "WelcomeWebview",
}

const args = {
  invocationPoint: LaunchTutorialCommandInvocationPoint.RecentWorkspacesPanel,
};
const encodedArgs = encodeURIComponent(JSON.stringify(args));
const commandUri = `command:sail.launchTutorialWorkspace?${encodedArgs}`;

export const DENDRON_VIEWS_WELCOME = [
  {
    view: SailTreeViewKey.BACKLINKS,
    contents: "There are no backlinks to this note.",
  },
  {
    view: SailTreeViewKey.RECENT_WORKSPACES,
    contents: `No recent workspaces detected. If this is your first time using Sail, [try out our tutorial workspace](${commandUri}).`,
  },
  {
    view: SailTreeViewKey.TREE_VIEW,
    contents: "First open a Sail note to see the tree view.",
  },
];

export const DENDRON_VIEWS_CONTAINERS = {
  activitybar: [
    {
      id: "sail-view",
      title: "Sail",
      icon: "media/icons/simple.svg",
    },
  ],
};

export const DENDRON_VIEWS = [
  {
    ...treeViewConfig2VSCodeEntry(SailTreeViewKey.SAMPLE_VIEW),
    when: SailContext.DEV_MODE,
    where: "explorer",
  },
  {
    id: SailTreeViewKey.BACKLINKS,
    name: "Backlinks",
    when: `${SailContext.PLUGIN_ACTIVE} && shellExecutionSupported`,
    where: "sail-view",
  },
  {
    ...treeViewConfig2VSCodeEntry(SailTreeViewKey.TREE_VIEW),
    when: `${SailContext.PLUGIN_ACTIVE}`,
    where: "sail-view",
    icon: "media/icons/tree.svg",
  },
  {
    ...treeViewConfig2VSCodeEntry(SailTreeViewKey.LOOKUP_VIEW),
    when: `${SailContext.PLUGIN_ACTIVE} && ${SailContext.NOTE_LOOK_UP_ACTIVE} && ${SailContext.SHOULD_SHOW_LOOKUP_VIEW}`,
    where: "sail-view",
  },
  {
    ...treeViewConfig2VSCodeEntry(SailTreeViewKey.CALENDAR_VIEW),
    when: `${SailContext.PLUGIN_ACTIVE} && shellExecutionSupported`,
    where: "sail-view",
  },
  {
    id: SailTreeViewKey.RECENT_WORKSPACES,
    name: "Recent Sail Workspaces",
    where: "sail-view",
    when: `${SailContext.PLUGIN_NOT_ACTIVE} && shellExecutionSupported`,
  },
];

type KeyBinding = {
  key?: string;
  mac?: string;
  windows?: string;
  when?: string;
  args?: any;
};

type ConfigEntry = {
  key: string;
  description: string;
  type: "string" | "boolean" | "number";
  default?: any;
  enum?: string[];
  scope?: CommandEntry;
};

type Entry = {
  name: string;
  description: string;
  data: any;
};

type CommandEntry = {
  key: string;
  title: string;
  keybindings?: KeyBinding;
  icon?: string;
  // this will be used in `commandPalette` contribution point.
  when?: string;
  // this will be used in `commands` contribution point.
  enablement?: string;
};

const CMD_PREFIX = "Sail:";
export const ICONS = {
  LINK_CANDIDATE: "debug-disconnect",
  WIKILINK: "link",
  SCHEMA: "repo",
};
export const DENDRON_WORKSPACE_FILE = "sail.code-workspace";

export const DENDRON_REMOTE_VAULTS: Entry[] = [
  {
    name: "sail",
    description: "sail.so notes",
    data: "https://github.com/sailhq/sail-site.git",
  },
  {
    name: "aws",
    description: "aws notes",
    data: "https://github.com/sailhq/sail-aws-vault.git",
  },
  {
    name: "tldr",
    description: "cli tld",
    data: "https://github.com/kevinslin/seed-tldr.git",
  },
  {
    name: "xkcd",
    description: "all xkcd comics",
    data: "https://github.com/kevinslin/seed-xkcd.git",
  },
];

type CommandPaletteEntry = {
  command: string;
  when?: string;
};

// TODO: fomarlize
export const DENDRON_MENUS = {
  commandPalette: [] as CommandPaletteEntry[],
  "view/title": [
    /**
     * Sort orders are round-robined, if we add more orders and/or change ordering
     * of sort order THEN make sure to update the labels of the command since the labels
     * display the current backlink ordering that is being used.
     * */
    {
      command: "sail.backlinks.sortByLastUpdated",
      when: `view == sail.backlinks && ${SailContext.BACKLINKS_SORT_ORDER} == ${BacklinkPanelSortOrder.PathNames}`,
      group: "sort@1",
    },
    {
      command: "sail.backlinks.sortByLastUpdatedChecked",
      when: `view == sail.backlinks && ${SailContext.BACKLINKS_SORT_ORDER} == ${BacklinkPanelSortOrder.LastUpdated}`,
      group: "sort@1",
    },
    {
      command: "sail.backlinks.sortByPathNames",
      when: `view == sail.backlinks && ${SailContext.BACKLINKS_SORT_ORDER} == ${BacklinkPanelSortOrder.LastUpdated}`,
      group: "sort@2",
    },
    {
      command: "sail.backlinks.sortByPathNamesChecked",
      when: `view == sail.backlinks && ${SailContext.BACKLINKS_SORT_ORDER} == ${BacklinkPanelSortOrder.PathNames}`,
      group: "sort@2",
    },
    {
      command: "sail.backlinks.expandAll",
      when: "view == sail.backlinks",
      group: "navigation@2",
    },
    {
      command: "sail.treeView.labelByTitle",
      when: `view == sail.treeView && ${SailContext.TREEVIEW_TREE_ITEM_LABEL_TYPE} == ${TreeViewItemLabelTypeEnum.filename}`,
    },
    {
      command: "sail.treeView.labelByFilename",
      when: `view == sail.treeView && ${SailContext.TREEVIEW_TREE_ITEM_LABEL_TYPE} == ${TreeViewItemLabelTypeEnum.title}`,
    },
    {
      command: "sail.treeView.expandAll",
      when: `view == sail.treeView && ${SailContext.DEV_MODE}`,
      group: "navigation@2",
    },
    {
      command: "sail.treeView.createNote",
      when: `view == sail.treeView`,
      group: "navigation@2",
    },
  ],
  "explorer/context": [
    {
      when: "explorerResourceIsFolder && sail:pluginActive && workspaceFolderCount > 1 && shellExecutionSupported",
      command: "sail.vaultAdd",
      group: "2_workspace",
    },
    {
      when: "explorerResourceIsFolder && sail:pluginActive && shellExecutionSupported",
      command: "sail.removeVault",
      group: "2_workspace",
    },
    {
      // [[Command Enablement / When Clause Gotchas|sail://sail.docs/pkg.plugin-core.t.commands.ops#command-enablement--when-clause-gotchas]]
      when: "resourceExtname == .md && sail:pluginActive && shellExecutionSupported || resourceExtname == .yml && sail:pluginActive && shellExecutionSupported",
      command: "sail.delete",
      group: "2_workspace",
    },
    {
      when: "resourceExtname == .md && sail:pluginActive && shellExecutionSupported",
      command: "sail.moveNote",
      group: "2_workspace",
    },
    {
      command: "sail.togglePreview",
      // when is the same as the built-in preview, plus pluginActive
      when: "resourceLangId == markdown && sail:pluginActive",
      group: "navigation",
    },
  ],
  "editor/context": [
    {
      when: "resourceExtname == .md && sail:pluginActive && shellExecutionSupported",
      command: "sail.copyNoteLink",
      group: "2_workspace",
    },
  ],
  "editor/title": [
    {
      command: "sail.togglePreview",
      // when is the same as the built-in preview, plus pluginActive
      when: "editorLangId == markdown && !notebookEditorFocused && sail:pluginActive",
      group: "navigation",
    },
  ],
  "editor/title/context": [
    {
      command: "sail.togglePreview",
      when: "resourceLangId == markdown && sail:pluginActive",
      group: "1_open",
    },
  ],
  "view/item/context": [
    {
      command: "sail.delete",
      when: "view == sail.treeView && viewItem == note && shellExecutionSupported",
    },
    {
      command: "sail.createNote",
      when: "view == sail.treeView && shellExecutionSupported",
    },
    {
      command: "sail.treeView.gotoNote",
      when: "view == sail.treeView && viewItem == stub && shellExecutionSupported",
      group: "inline",
    },
  ],
};

export const DENDRON_COMMANDS: { [key: string]: CommandEntry } = {
  // --- zotero 
  ZOTERO_CITATION_PICK: {
    key: "sail.zotero.citationPick",
    title: `${CMD_PREFIX} Zotero: Pick Citation`,
  },
  // --- backlinks panel buttons
  BACKLINK_SORT_BY_LAST_UPDATED: {
    key: "sail.backlinks.sortByLastUpdated",
    title: "Sort by Last Updated",
  },
  BACKLINK_SORT_BY_LAST_UPDATED_CHECKED: {
    key: "sail.backlinks.sortByLastUpdatedChecked",
    title: "✓ Sort by Last Updated",
  },
  BACKLINK_SORT_BY_PATH_NAMES: {
    key: "sail.backlinks.sortByPathNames",
    title: "Sort by Path Names",
  },
  BACKLINK_SORT_BY_PATH_NAMES_CHECKED: {
    key: "sail.backlinks.sortByPathNamesChecked",
    title: "✓ Sort by Path Names",
  },
  BACKLINK_EXPAND_ALL: {
    key: "sail.backlinks.expandAll",
    title: "Expand All",
    icon: "$(expand-all)",
  },
  // --- tree view panel buttons
  TREEVIEW_LABEL_BY_TITLE: {
    key: "sail.treeView.labelByTitle",
    title: "Label and sort notes by title",
    icon: "$(list-ordered)",
  },
  TREEVIEW_LABEL_BY_FILENAME: {
    key: "sail.treeView.labelByFilename",
    title: "Label and sort notes by filename",
    icon: "$(list-ordered)",
  },
  TREEVIEW_EXPAND_ALL: {
    key: "sail.treeView.expandAll",
    title: "Expand All",
    icon: "$(expand-all)",
    when: SailContext.DEV_MODE,
  },
  TREEVIEW_CREATE_NOTE: {
    key: "sail.treeView.createNote",
    title: "Create Note",
    icon: "$(new-file)",
    when: "false",
  },
  TREEVIEW_EXPAND_STUB: {
    key: "sail.treeView.expandStub",
    title: `${CMD_PREFIX} Dev: Expand Stub`,
    when: "false",
  },
  TREEVIEW_GOTO_NOTE: {
    key: "sail.treeView.gotoNote",
    title: `Create Note`, // will appear in the tooltip
    icon: "$(gist-new)",
    when: "false",
  },
  // --- Notes
  BROWSE_NOTE: {
    key: "sail.browseNote",
    title: `${CMD_PREFIX} Browse Note`,
    when: `${SailContext.PLUGIN_ACTIVE} && shellExecutionSupported`,
  },
  GOTO: {
    key: "sail.goto",
    title: `${CMD_PREFIX} Go to`,
    when: `${SailContext.PLUGIN_ACTIVE} && shellExecutionSupported`,
    keybindings: {
      when: "editorFocus",
    },
  },
  GOTO_NOTE: {
    key: "sail.gotoNote",
    title: `${CMD_PREFIX} Go to Note`,
    when: `${SailContext.PLUGIN_ACTIVE} && shellExecutionSupported`,
    keybindings: {
      key: "ctrl+k g",
      when: "editorFocus",
    },
  },
  GOTO_TODAY_NOTE: {
    key: "sail.gotoToday",
    title: `${CMD_PREFIX} Go to Today`,
    when: `${SailContext.PLUGIN_ACTIVE} && shellExecutionSupported`,
  },
  CREATE_SCHEMA_FROM_HIERARCHY: {
    key: "sail.createSchemaFromHierarchy",
    title: `${CMD_PREFIX} Create Schema From Note Hierarchy`,
    keybindings: {
      when: `editorFocus && ${SailContext.PLUGIN_ACTIVE}`,
    },
    when: `${SailContext.PLUGIN_ACTIVE} && shellExecutionSupported`,
  },
  CREATE_DAILY_JOURNAL_NOTE: {
    key: "sail.createDailyJournalNote",
    title: `${CMD_PREFIX} Create Daily Journal Note`,
    keybindings: {
      key: "ctrl+shift+i",
      mac: "cmd+shift+i",
      when: `${SailContext.PLUGIN_ACTIVE} && shellExecutionSupported`,
    },
    when: `${SailContext.PLUGIN_ACTIVE} && shellExecutionSupported`,
  },
  COPY_NOTE_LINK: {
    key: "sail.copyNoteLink",
    title: `${CMD_PREFIX} Copy Note Link`,
    keybindings: {
      key: "ctrl+shift+c",
      mac: "cmd+shift+c",
      when: `editorFocus && ${SailContext.PLUGIN_ACTIVE}`,
    },
    when: `${SailContext.PLUGIN_ACTIVE} && shellExecutionSupported`,
  },
  COPY_NOTE_REF: {
    key: "sail.copyNoteRef",
    title: `${CMD_PREFIX} Copy Note Ref`,
    keybindings: {
      key: "ctrl+shift+r",
      mac: "cmd+shift+r",
      when: `editorFocus && ${SailContext.PLUGIN_ACTIVE}`,
    },
    when: `${SailContext.PLUGIN_ACTIVE} && shellExecutionSupported`,
  },
  COPY_TO_CLIPBOARD: {
    key: "sail.copyToClipboard",
    title: `${CMD_PREFIX} Copy To Clipboard`,
    when: "false",
  },
  COPY_AS: {
    key: "sail.copyAs",
    title: `${CMD_PREFIX} Copy As`,
    keybindings: {
      key: "ctrl+k ctrl+c",
      mac: "cmd+k cmd+c",
      when: "sail:pluginActive",
    },
    when: `${SailContext.PLUGIN_ACTIVE} && shellExecutionSupported`,
  },
  DELETE: {
    key: "sail.delete",
    title: `${CMD_PREFIX} Delete`,
    keybindings: {
      key: "ctrl+shift+d",
      mac: "cmd+shift+d",
      when: `${SailContext.PLUGIN_ACTIVE} && shellExecutionSupported`,
    },
    when: `${SailContext.PLUGIN_ACTIVE} && shellExecutionSupported`,
  },
  INSERT_NOTE_LINK: {
    key: "sail.insertNoteLink",
    title: `${CMD_PREFIX} Insert Note Link`,
    when: `${SailContext.PLUGIN_ACTIVE} && shellExecutionSupported`,
  },
  INSERT_NOTE_INDEX: {
    key: "sail.insertNoteIndex",
    title: `${CMD_PREFIX} Insert Note Index`,
    when: `${SailContext.PLUGIN_ACTIVE} && shellExecutionSupported`,
  },
  MOVE_NOTE: {
    key: "sail.moveNote",
    title: `${CMD_PREFIX} Move Note`,
    when: `${SailContext.PLUGIN_ACTIVE} && shellExecutionSupported`,
  },
  MOVE_SELECTION_TO: {
    key: "sail.moveSelectionTo",
    title: `${CMD_PREFIX} Move Selection To`,
    when: `${SailContext.PLUGIN_ACTIVE} && shellExecutionSupported`,
  },
  MERGE_NOTE: {
    key: "sail.mergeNote",
    title: `${CMD_PREFIX} Merge Note`,
    when: `${SailContext.PLUGIN_ACTIVE} && shellExecutionSupported`,
  },
  RANDOM_NOTE: {
    key: "sail.randomNote",
    title: `${CMD_PREFIX} Random Note`,
    when: `${SailContext.PLUGIN_ACTIVE} && shellExecutionSupported`,
  },
  RENAME_NOTE_INTERNAL: {
    key: "sail.renameNoteV2a",
    title: `${CMD_PREFIX} Rename Note V2a`,
    when: "false", // this is internal only.
  },
  RENAME_NOTE: {
    key: "sail.renameNote",
    title: `${CMD_PREFIX} Rename Note`,
    when: `${SailContext.PLUGIN_ACTIVE} && shellExecutionSupported`,
  },
  BATCH_RENAME_NOTE: {
    key: "sail.batchRenameNote",
    title: `${CMD_PREFIX} Batch Rename Note`,
    when: `${SailContext.PLUGIN_ACTIVE} && shellExecutionSupported`,
  },
  RENAME_HEADER: {
    key: "sail.renameHeader",
    title: `${CMD_PREFIX} Rename Header`,
    when: `${SailContext.PLUGIN_ACTIVE} && shellExecutionSupported`,
  },
  MOVE_HEADER: {
    key: "sail.moveHeader",
    title: `${CMD_PREFIX} Move Header`,
    when: `${SailContext.PLUGIN_ACTIVE} && shellExecutionSupported`,
  },
  CONVERT_CANDIDATE_LINK: {
    key: "sail.convertCandidateLink",
    title: `${CMD_PREFIX} Convert Candidate Link`,
    when: "false",
  },
  CONVERT_LINK: {
    key: "sail.convertLink",
    title: `${CMD_PREFIX} Convert Link`,
    when: `${SailContext.PLUGIN_ACTIVE} && shellExecutionSupported`,
  },
  LOOKUP_NOTE: {
    key: "sail.lookupNote",
    title: `${CMD_PREFIX} Lookup Note`,
    keybindings: {
      mac: "cmd+L",
      key: "ctrl+l",
      when: `${SailContext.PLUGIN_ACTIVE}`,
    },
    when: `${SailContext.PLUGIN_ACTIVE}`,
  },

  // This command will only apply when the note look up quick pick is open
  // which is taken care by the SailContext.NOTE_LOOK_UP_ACTIVE
  //
  // It will also NOT activate when the focus is in editor using `!editorFocus`
  //
  // However, when it comes to user navigating to side panels its quite imperfect.
  // We do have some protection against Tab interception by using the `!view`
  // (most side panels set the view variable Eg. "view": "sail.backlinks").
  // But it is possible for user to tab into empty side panel which does not
  // have a `view` context set, at that point if user still has look up open and
  // presses tab, Tab will get intercepted by note auto complete.
  //
  // Ideally there would be a trigger event when quick pick goes in focus/focuses out
  // but not able to find such hook.
  LOOKUP_NOTE_AUTO_COMPLETE: {
    key: "sail.lookupNoteAutoComplete",

    /** This command will NOT show up within the command palette
     *  since its disabled within package.json in contributes.menus.commandPalette */
    title: `${CMD_PREFIX} hidden`,
    keybindings: {
      key: "Tab",
      when: `${SailContext.PLUGIN_ACTIVE} && ${SailContext.NOTE_LOOK_UP_ACTIVE} && !editorFocus && !view`,
    },
    when: `${SailContext.PLUGIN_ACTIVE} && ${SailContext.NOTE_LOOK_UP_ACTIVE} && !editorFocus && !view`,
  },
  CREATE_JOURNAL: {
    key: "sail.createJournalNote",
    title: `${CMD_PREFIX} Create Journal Note`,
    keybindings: {
      key: "ctrl+shift+j",
      mac: "cmd+shift+j",
      args: {
        noteType: "journal",
      },
      when: `${SailContext.PLUGIN_ACTIVE} && shellExecutionSupported`,
    },
    when: `${SailContext.PLUGIN_ACTIVE} && shellExecutionSupported`,
  },
  CREATE_SCRATCH: {
    key: "sail.createScratchNote",
    title: `${CMD_PREFIX} Create Scratch Note`,
    keybindings: {
      key: "ctrl+k s",
      mac: "cmd+k s",
      when: `${SailContext.PLUGIN_ACTIVE} && shellExecutionSupported`,
    },
    when: `${SailContext.PLUGIN_ACTIVE} && shellExecutionSupported`,
  },
  CREATE_NOTE: {
    key: "sail.createNote",
    title: `${CMD_PREFIX} Create Note`,
    when: `${SailContext.PLUGIN_ACTIVE} && shellExecutionSupported`,
  },
  CREATE_MEETING_NOTE: {
    key: "sail.createMeetingNote",
    title: `${CMD_PREFIX} Create Meeting Note`,
    when: `${SailContext.PLUGIN_ACTIVE} && shellExecutionSupported`,
  },
  LOOKUP_SCHEMA: {
    key: "sail.lookupSchema",
    title: `${CMD_PREFIX} Lookup Schema`,
    keybindings: {
      mac: "cmd+shift+L",
      key: "ctrl+shift+l",
      when: `${SailContext.PLUGIN_ACTIVE} && shellExecutionSupported`,
    },
    when: `${SailContext.PLUGIN_ACTIVE} && shellExecutionSupported`,
  },
  RELOAD_INDEX: {
    key: "sail.reloadIndex",
    title: `${CMD_PREFIX} Reload Index`,
    when: `${SailContext.PLUGIN_ACTIVE} && shellExecutionSupported`,
  },
  TASK_CREATE: {
    key: "sail.createTask",
    title: `${CMD_PREFIX} Create Task Note`,
    when: `${SailContext.PLUGIN_ACTIVE} && shellExecutionSupported`,
  },
  TASK_SET_STATUS: {
    key: "sail.setTaskStatus",
    title: `${CMD_PREFIX} Set Task Status`,
    when: `${SailContext.PLUGIN_ACTIVE} && shellExecutionSupported`,
  },
  TASK_COMPLETE: {
    key: "sail.completeTask",
    title: `${CMD_PREFIX} Complete Task`,
    when: `${SailContext.PLUGIN_ACTIVE} && shellExecutionSupported`,
  },
  APPLY_TEMPLATE: {
    key: "sail.applyTemplate",
    title: `${CMD_PREFIX} Apply Template`,
    when: `${SailContext.PLUGIN_ACTIVE} && shellExecutionSupported`,
  },
  // --- Hierarchies
  ARCHIVE_HIERARCHY: {
    key: "sail.archiveHierarchy",
    title: `${CMD_PREFIX} Archive Hierarchy`,
    when: `${SailContext.PLUGIN_ACTIVE} && shellExecutionSupported`,
  },
  REFACTOR_HIERARCHY: {
    key: "sail.refactorHierarchy",
    title: `${CMD_PREFIX} Refactor Hierarchy`,
    when: `${SailContext.PLUGIN_ACTIVE} && shellExecutionSupported`,
  },
  GO_UP_HIERARCHY: {
    key: "sail.goUpHierarchy",
    title: `${CMD_PREFIX} Go Up`,
    keybindings: {
      mac: "cmd+shift+up",
      key: "ctrl+shift+up",
      when: `editorFocus && ${SailContext.PLUGIN_ACTIVE}`,
    },
    when: `${SailContext.PLUGIN_ACTIVE} && shellExecutionSupported`,
  },
  GO_NEXT_HIERARCHY: {
    key: "sail.goNextHierarchy",
    title: `${CMD_PREFIX} Go Next Sibling`,
    keybindings: {
      key: "ctrl+shift+]",
      when: `editorFocus && ${SailContext.PLUGIN_ACTIVE}`,
    },
    when: `${SailContext.PLUGIN_ACTIVE} && shellExecutionSupported`,
  },
  GO_PREV_HIERARCHY: {
    key: "sail.goPrevHierarchy",
    title: `${CMD_PREFIX} Go Previous Sibling`,
    keybindings: {
      key: "ctrl+shift+[",
      when: `editorFocus && ${SailContext.PLUGIN_ACTIVE}`,
    },
    when: `${SailContext.PLUGIN_ACTIVE} && shellExecutionSupported`,
  },
  GO_DOWN_HIERARCHY: {
    key: "sail.goDownHierarchy",
    title: `${CMD_PREFIX} Go Down`,
    keybindings: {
      mac: "cmd+shift+down",
      key: "ctrl+shift+down",
      when: `editorFocus && ${SailContext.PLUGIN_ACTIVE}`,
    },
    when: `${SailContext.PLUGIN_ACTIVE} && shellExecutionSupported`,
  },
  GOTO_BACKLINK: {
    key: "sail.gotoBacklink",
    title: `${CMD_PREFIX} Go To Backlink`,
    when: "false",
  },
  // --- Workspace
  ADD_AND_COMMIT: {
    key: "sail.addAndCommit",
    title: `${CMD_PREFIX} Workspace: Add and Commit`,
    when: `${SailContext.PLUGIN_ACTIVE} && shellExecutionSupported`,
  },
  SYNC: {
    key: "sail.sync",
    title: `${CMD_PREFIX} Workspace: Sync`,
    when: `${SailContext.PLUGIN_ACTIVE} && shellExecutionSupported`,
  },
  VAULT_ADD: {
    key: "sail.vaultAdd",
    title: `${CMD_PREFIX} Vault Add`,
    when: `${SailContext.PLUGIN_ACTIVE} && shellExecutionSupported`,
  },
  REMOVE_VAULT: {
    key: "sail.removeVault",
    title: `${CMD_PREFIX} Remove Vault`,
    when: `${SailContext.PLUGIN_ACTIVE} && shellExecutionSupported`,
  },
  CONVERT_VAULT: {
    key: "sail.convertVault",
    title: `${CMD_PREFIX} Convert Vault`,
    when: `${SailContext.PLUGIN_ACTIVE} && shellExecutionSupported`,
  },
  CREATE_NEW_VAULT: {
    key: "sail.createNewVault",
    title: `${CMD_PREFIX} Create New Vault`,
    when: `${SailContext.PLUGIN_ACTIVE} && shellExecutionSupported`,
  },
  ADD_EXISTING_VAULT: {
    key: "sail.addExistingVault",
    title: `${CMD_PREFIX} Add Existing Vault`,
    when: `${SailContext.PLUGIN_ACTIVE} && shellExecutionSupported`,
  },
  INIT_WS: {
    key: "sail.initWS",
    title: `${CMD_PREFIX} Initialize Workspace`,
    when: "shellExecutionSupported",
  },
  CHANGE_WS: {
    key: "sail.changeWS",
    title: `${CMD_PREFIX} Change Workspace`,
    when: "shellExecutionSupported",
  },
  UPGRADE_SETTINGS: {
    key: "sail.upgradeSettings",
    title: `${CMD_PREFIX} Upgrade Settings`,
    when: `${SailContext.PLUGIN_ACTIVE} && shellExecutionSupported`,
  },
  COPY_NOTE_URL: {
    key: "sail.copyNoteURL",
    title: `${CMD_PREFIX} Copy Note URL`,
    keybindings: {
      mac: "cmd+shift+u",
      windows: "ctrl+shift+u",
      when: `editorFocus && ${SailContext.PLUGIN_ACTIVE}`,
    },
    when: `${SailContext.PLUGIN_ACTIVE}`,
  },
  // --- Hooks
  CREATE_HOOK: {
    key: "sail.createHook",
    title: `${CMD_PREFIX} Hook Create`,
    when: `${SailContext.PLUGIN_ACTIVE} && shellExecutionSupported`,
  },
  DELETE_HOOK: {
    key: "sail.deleteHook",
    title: `${CMD_PREFIX} Hook Delete`,
    when: `${SailContext.PLUGIN_ACTIVE} && shellExecutionSupported`,
  },
  REGISTER_NOTE_TRAIT: {
    key: "sail.registerNoteTrait",
    title: `${CMD_PREFIX} Register Note Trait`,
    when: "false",
  },
  CONFIGURE_NOTE_TRAITS: {
    key: "sail.configureNoteTraits",
    title: `${CMD_PREFIX} Configure Note Traits`,
    when: `${SailContext.PLUGIN_ACTIVE} && shellExecutionSupported`,
  },
  CREATE_USER_DEFINED_NOTE: {
    key: "sail.createNoteWithTraits",
    title: `${CMD_PREFIX} Create Note with Custom Traits`,
    when: `${SailContext.PLUGIN_ACTIVE} && shellExecutionSupported`,
  },
  // --- Misc
  OPEN_LINK: {
    key: "sail.openLink",
    title: `${CMD_PREFIX} Open Link`,
    when: `false`,
  },
  PASTE_LINK: {
    key: "sail.pasteLink",
    title: `${CMD_PREFIX} Paste Link`,
    when: `${SailContext.PLUGIN_ACTIVE} && shellExecutionSupported`,
  },
  SHOW_HELP: {
    key: "sail.showHelp",
    title: `${CMD_PREFIX} Show Help`,
    when: "shellExecutionSupported",
  },
  SHOW_NOTE_GRAPH: {
    key: "sail.showNoteGraphView",
    title: `${CMD_PREFIX} Show Note Graph`,
    when: `${SailContext.PLUGIN_ACTIVE} && shellExecutionSupported`,
  },
  SHOW_SCHEMA_GRAPH: {
    key: "sail.showSchemaGraphView",
    title: `${CMD_PREFIX} Show Schema Graph`,
    when: `${SailContext.PLUGIN_ACTIVE} && shellExecutionSupported`,
  },
  TOGGLE_PREVIEW: {
    key: "sail.togglePreview",
    title: `${CMD_PREFIX} Toggle Preview`,
    icon: `$(open-preview)`,
    keybindings: {
      key: "ctrl+k v",
      mac: "cmd+ctrl+p",
      when: "sail:pluginActive",
    },
    when: "sail:pluginActive",
  },
  TOGGLE_PREVIEW_LOCK: {
    key: "sail.togglePreviewLock",
    title: `${CMD_PREFIX} Toggle Preview Lock`,
    icon: `$(lock)`,
    when: "sail:pluginActive",
  },
  // --- SailZen Doc Export
  EXPORT_NOTE: {
    key: "sailzen.exportNote",
    title: `SailZen: Export Note`,
    when: `${SailContext.PLUGIN_ACTIVE} && shellExecutionSupported`,
  },
  COMPILE_DOCUMENT: {
    key: "sailzen.compileDocument",
    title: `SailZen: Compile Document`,
    when: `${SailContext.PLUGIN_ACTIVE} && shellExecutionSupported`,
  },
  PASTE_FILE: {
    key: "sail.pasteFile",
    title: `${CMD_PREFIX} Paste File`,
    when: `${SailContext.PLUGIN_ACTIVE} && shellExecutionSupported`,
  },
  // -- Workbench
  CONFIGURE_RAW: {
    key: "sail.configureRaw",
    title: `${CMD_PREFIX} Configure (yaml)`,
    when: `${SailContext.PLUGIN_ACTIVE} && shellExecutionSupported`,
  },

  CONFIGURE_UI: {
    key: "sail.configureUI",
    title: `${CMD_PREFIX} Configure (UI)`,
    when: `${SailContext.PLUGIN_ACTIVE} && shellExecutionSupported`,
  },
  CONFIGURE_GRAPH_STYLES: {
    key: "sail.configureGraphStyle",
    title: `${CMD_PREFIX} Configure Graph Style (css)`,
    when: `${SailContext.PLUGIN_ACTIVE} && shellExecutionSupported`,
  },
  CONFIGURE_LOCAL_OVERRIDE: {
    key: "sail.configureLocalOverride",
    title: `${CMD_PREFIX} Configure Local Override`,
    when: `${SailContext.PLUGIN_ACTIVE} && shellExecutionSupported`,
  },
  // --- Dev
  DOCTOR: {
    key: "sail.dev.doctor",
    title: `${CMD_PREFIX} Doctor`,
    when: `${SailContext.PLUGIN_ACTIVE} && shellExecutionSupported`,
  },
  DUMP_STATE: {
    key: "sail.dev.dumpState",
    title: `${CMD_PREFIX} Dump State`,
    when: `${SailContext.PLUGIN_ACTIVE} && shellExecutionSupported`,
  },
  DEV_TRIGGER: {
    key: "sail.dev.devTrigger",
    title: `${CMD_PREFIX}Dev: Dev Trigger`,
    when: SailContext.DEV_MODE,
  },
  RESET_CONFIG: {
    key: "sail.dev.resetConfig",
    title: `${CMD_PREFIX}Dev: Reset Config`,
    when: "shellExecutionSupported",
  },
  OPEN_LOGS: {
    key: "sail.dev.openLogs",
    title: `${CMD_PREFIX}Dev: Open Logs`,
    when: "shellExecutionSupported",
  },
  DEV_DIAGNOSTICS_REPORT: {
    key: "sail.diagnosticsReport",
    title: `${CMD_PREFIX}Dev: Diagnostics Report`,
    when: `${SailContext.PLUGIN_ACTIVE} && shellExecutionSupported`,
  },
  OPEN_BACKUP: {
    key: "sail.openBackup",
    title: `${CMD_PREFIX} Open Backup`,
    when: `${SailContext.PLUGIN_ACTIVE} && shellExecutionSupported`,
  },
  VALIDATE_ENGINE: {
    key: "sail.dev.validateEngine",
    title: `${CMD_PREFIX}Dev: Validate Engine`,
    when: `${SailContext.PLUGIN_ACTIVE} && shellExecutionSupported`,
  },
};

export const DENDRON_CHANNEL_NAME = "Sail";

export const WORKSPACE_STATE = {
  VERSION: "sail.wsVersion",
};

export enum GLOBAL_STATE {
  VERSION = "sail.version",
  /**
   * Context that can be used on extension activation to trigger special behavior.
   */
  WORKSPACE_ACTIVATION_CONTEXT = "sail.workspace_activation_context",
  /**
   * Extension is being debugged
   */
  VSCODE_DEBUGGING_EXTENSION = "sail.vscode_debugging_extension",
  /**
   * Most Recently Imported Doc
   */
  MRUDocs = "MRUDocs",
  /**
   * @deprecated
   * Checks if initial survey was prompted and submitted.
   */
  INITIAL_SURVEY_SUBMITTED = "sail.initial_survey_submitted",
  /**
   * @deprecated
   * Checks if lapsed user survey was submitted.
   */
  LAPSED_USER_SURVEY_SUBMITTED = "sail.lapsed_user_survey_submitted",
  /**
   * @deprecated
   * Chekcs if inactive user survey was submitted.
   */
  INACTIVE_USER_SURVEY_SUBMITTED = "sail.inactive_user_survey_submitted",
}

/**
 * @deprecated
 */
export enum WORKSPACE_ACTIVATION_CONTEXT {
  // UNSET - Indicates this is the first Workspace Launch
  "NORMAL", // Normal Launch; No Special Behavior
  "TUTORIAL", // Launch the Tutorial
  "SEED_BROWSER", // Open with Seed Browser Webview
}

export type ConfigKey = keyof typeof CONFIG;

export const _noteAddBehaviorEnum = [
  "childOfDomain",
  "childOfDomainNamespace",
  "childOfCurrent",
  "asOwnDomain",
];

export const CONFIG: { [key: string]: ConfigEntry } = {
  // --- journals
  DAILY_JOURNAL_DOMAIN: {
    key: "sail.dailyJournalDomain",
    type: "string",
    default: "daily",
    description: "DEPRECATED. Use journal settings in sail.yml",
  },
  DEFAULT_JOURNAL_NAME: {
    key: "sail.defaultJournalName",
    type: "string",
    default: "journal",
    description: "DEPRECATED. Use journal settings in sail.yml",
  },
  DEFAULT_JOURNAL_DATE_FORMAT: {
    key: "sail.defaultJournalDateFormat",
    type: "string",
    default: "y.MM.dd",
    description: "DEPRECATED. Use journal settings in sail.yml",
  },
  DEFAULT_JOURNAL_ADD_BEHAVIOR: {
    key: "sail.defaultJournalAddBehavior",
    default: "childOfDomain",
    type: "string",
    description: "DEPRECATED. Use journal settings in sail.yml",
    enum: _noteAddBehaviorEnum,
  },
  DEFAULT_SCRATCH_NAME: {
    key: "sail.defaultScratchName",
    type: "string",
    default: "scratch",
    description: "DEPRECATED. Use scratch settings in sail.yml",
  },
  DEFAULT_SCRATCH_DATE_FORMAT: {
    key: "sail.defaultScratchDateFormat",
    type: "string",
    default: "y.MM.dd.HHmmss",
    description: "DEPRECATED. Use scratch settings in sail.yml",
  },
  DEFAULT_SCRATCH_ADD_BEHAVIOR: {
    key: "sail.defaultScratchAddBehavior",
    default: "asOwnDomain",
    type: "string",
    description: "DEPRECATED. Use scratch settings in sail.yml",
    enum: _noteAddBehaviorEnum,
  },
  COPY_NOTE_URL_ROOT: {
    key: "sail.copyNoteUrlRoot",
    type: "string",
    description: "override root url when getting note url",
  },
  LINK_SELECT_AUTO_TITLE_BEHAVIOR: {
    key: "sail.linkSelectAutoTitleBehavior",
    type: "string",
    description: "Control title behavior when using selection2link with lookup",
    enum: ["none", "slug"],
    default: "slug",
  },
  DEFAULT_LOOKUP_CREATE_BEHAVIOR: {
    key: "sail.defaultLookupCreateBehavior",
    default: "selectionExtract",
    type: "string",
    description:
      "when creating a new note with selected text, define behavior for selected text",
    enum: ["selection2link", "selectionExtract"],
  },
  // --- timestamp decoration
  DEFAULT_TIMESTAMP_DECORATION_FORMAT: {
    key: CodeConfigKeys.DEFAULT_TIMESTAMP_DECORATION_FORMAT,
    default: "DATETIME_MED",
    type: "string",
    description: "Decide how human readable timestamp decoration is displayed",
    enum: [
      "DATETIME_FULL",
      "DATETIME_FULL_WITH_SECONDS",
      "DATETIME_HUGE",
      "DATETIME_HUGE_WITH_SECONDS",
      "DATETIME_MED",
      "DATETIME_MED_WITH_SECONDS",
      "DATETIME_SHORT",
      "DATETIME_SHORT_WITH_SECONDS",
      "DATE_FULL",
      "DATE_HUGE",
      "DATE_MED",
      "DATE_MED_WITH_WEEKDAY",
      "DATE_SHORT",
      "TIME_24_SIMPLE",
      "TIME_24_WITH_LONG_OFFSET",
      "TIME_24_WITH_SECONDS",
      "TIME_24_WITH_SHORT_OFFSET",
      "TIME_SIMPLE",
      "TIME_WITH_LONG_OFFSET",
      "TIME_WITH_SECONDS",
      "TIME_WITH_SHORT_OFFSET",
    ],
  },
  // --- root dir
  ROOT_DIR: {
    key: "sail.rootDir",
    type: "string",
    default: "",
    description: "location of sail workspace",
  },
  DENDRON_DIR: {
    key: "sail.sailDir",
    type: "string",
    default: "",
    description: "DEPRECATED. Use journal settings in sail.yml",
  },
  // --- other
  LOG_LEVEL: {
    key: "sail.logLevel",
    type: "string",
    default: "info",
    description: "control verbosity of sail logs",
    enum: ["debug", "info", "error"],
  },
  LSP_LOG_LVL: {
    key: "sail.trace.server",
    enum: ["off", "messages", "verbose"],
    type: "string",
    default: "messages",
    description: "LSP log level",
  },
  SERVER_PORT: {
    key: "sail.serverPort",
    type: "number",
    description:
      "port for server. If not set, will be randomly generated at startup.",
  },
  ENABLE_SELF_CONTAINED_VAULT_WORKSPACE: {
    key: DENDRON_VSCODE_CONFIG_KEYS.ENABLE_SELF_CONTAINED_VAULTS_WORKSPACE,
    type: "boolean",
    default: true,
    description:
      "When enabled, newly created workspaces will be created as self contained vaults.",
  },
};

export const gdocRequiredScopes = [
  "https://www.googleapis.com/auth/documents",
  "https://www.googleapis.com/auth/drive",
];

export const INCOMPATIBLE_EXTENSIONS = [
  "yzhang.markdown-all-in-one",
  "fantasy.markdown-all-in-one-for-web",
  "foam.foam-vscode",
  "brianibbotson.add-double-bracket-notation-to-selection",
  "ianjsikes.md-graph",
  "thomaskoppelaar.markdown-wiki-links-preview",
  "svsool.markdown-memo",
  "kortina.vscode-markdown-notes",
  "maxedmands.vscode-zettel-markdown-notes",
  "tchayen.markdown-links",
  // Note graph is now built into Sail, and having this extension enabled breaks it.
  "sail.sail-markdown-links",
];

export type osType = "Linux" | "Darwin" | "Windows_NT";

export function isOSType(str: string): str is osType {
  return str === "Linux" || str === "Darwin" || str === "Windows_NT";
}

export type KeybindingConflict = {
  /**
   * extension id of the extension that has keybinding conflict
   */
  extensionId: string;
  /**
   * command id of the command contributed by `extensionId` that conflicts
   */
  commandId: string;
  /**
   * command id of Sail command that conflicts with `commandId`
   */
  conflictsWith: string;
  /**
   * os in which this conflict exists. assume all platforms if undefined.
   * this is the os type returned by {@link os.type}
   */
  os?: osType[];
};

export const KNOWN_CONFLICTING_EXTENSIONS = ["vscodevim.vim"];

/**
 * List of known keybinding conflicts
 */
export const KNOWN_KEYBINDING_CONFLICTS: KeybindingConflict[] = [
  {
    extensionId: "vscodevim.vim",
    commandId: "extension.vim_navigateCtrlL",
    conflictsWith: "sail.lookupNote",
    os: ["Linux", "Windows_NT"],
  },
  // This is left here so it could be tested in Darwin.
  // This is not an actual conflict.
  // {
  //   extensionId: "vscodevim.vim",
  //   commandId: "extension.vim_tab",
  //   conflictsWith: "sail.lookupNoteAutoComplete",
  // },
];

