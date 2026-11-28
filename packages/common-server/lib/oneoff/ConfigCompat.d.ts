import { SailConfig, SailDevConfig, SailError, DHookDict, DVault, DVaultSync, WorkspaceSettings } from "@saili/common-all";
export type MigrationChangeSetStatus = {
    error?: SailError;
    data: {
        version: string;
        changeName: string;
        status: "ok" | "error";
        sailConfig: SailConfig;
        wsConfig?: WorkspaceSettings;
    };
};
type mappedConfigPath = {
    /**
     * legacy config path to target.
     */
    target: string;
    /**
     * How we want to map the config.
     * if "skip", don't map.
     *   use this when it is a namespace that itself has properties.
     * if undefined, identity mapping is assumed (_.identity)
     */
    iteratee?: Function | "skip";
    /**
     * Set to true to mark that legacy path should be preserved.
     */
    preserve?: boolean;
};
export declare const PATH_MAP: Map<string, mappedConfigPath>;
type SailConfigV4 = {
    /**
     * Disable caching behavior
     */
    noCaching?: boolean;
    /** Maximum number of rendered previews to cache in Sail Engine.
     *  Note: this value is ignored when {@link SailConfig.noCaching} is set to true.
     *  When set this value must be greater than 0. */
    maxPreviewsCached?: number;
    /**
     * Disable telemetry
     */
    noTelemetry?: boolean;
    /**
     * Sail version. Setup by plugin
     @deprecated
     */
    version: number;
    /**
     * Sail version
     */
    sailVersion?: string;
    /**
     * Configuration related to publishing notes
     */
    site: SailSiteConfig;
    /**
     * Configuration related to lookup v3.
     */
    lookup: LegacyLookupConfig;
    journal: LegacyJournalConfig;
    scratch?: LegacyScratchConfig;
    insertNoteLink?: LegacyInsertNoteLinkConfig;
    /**
     * Workspaces
     */
    workspaces?: {
        [key: string]: any | undefined;
    };
    seeds?: {
        [key: string]: any | undefined;
    };
    /**
     * Sail vaults in workspace.
     * Setup by plugin.
     */
    vaults: DVault[];
    hooks?: DHookDict;
    /**
     * When set to true `Create New` will not bubble up to the top of lookup results.
     *
     * default: false.
     * */
    lookupDontBubbleUpCreateNew?: boolean;
    /**
     * Pick vault when creating new note.
     * [Docs](https://sail.so/notes/24b176f1-685d-44e1-a1b0-1704b1a92ca0.html#specify-vault-location-when-creating-a-note)
     */
    lookupConfirmVaultOnCreate?: boolean;
    /**
     * Use the title from frontmatter
     */
    useFMTitle?: boolean;
    /**
     * If true, use the note title when displaying naked links
     */
    useNoteTitleForLink?: boolean;
    /**
     * Enable mermaid diagram sytnax
     */
    mermaid?: boolean;
    /**
     * Use nunjucks templating
     */
    useNunjucks?: boolean;
    /**
     * Use pretty refs for preview
     */
    usePrettyRefs?: boolean;
    /**
     * Use katex for rendering math
     * default: true
     */
    useKatex?: boolean;
    /**
     * Should show hierarchy
     */
    hierarchyDisplay?: boolean;
    /**
     * Title used for hiearchies
     * Default: Children
     */
    hierarchyDisplayTitle?: string;
    /**
     * Configuration for note and schema graphs
     */
    graph?: LegacySailGraphConfig;
    /**
     * Don't automatically create note when looking up definition
     */
    noAutoCreateOnDefinition?: boolean;
    /**
     * Turn off legacy note refs;
     */
    noLegacyNoteRef?: boolean;
    /**
     * Disable xvault wiki links
     */
    noXVaultWikiLink?: boolean;
    /**
     * Initialize remote vaults on startup
     * Default: true
     */
    initializeRemoteVaults?: boolean;
    /**
     * If true, enable feedback widget
     */
    feedback?: boolean;
    /**
     * If using backend API functionality
     */
    apiEndpoint?: string;
    /**
     * Default is templates
     */
    defaultInsertHierarchy?: string;
    /**
     * Development related options
     */
    dev?: SailDevConfig;
    /**
     * How workspace vaults should be handled when using workspace "add and commit" and "sync" commands.
     *
     * Options are:
     * * skip: Skip them entirely. You must manage the repository manually.
     * * noPush: Commit any changes and pull updates, but don't push. You can watch the repository and make local changes without sharing them back.
     * * noCommit: Pull and push updates if the workspace is clean, but don't commit. You manually commit your local changes, but automatically share them once you committed.
     * * sync: Commit changes, and pull and push updates. Treats workspace vaults like regular vaults.
     *
     * Defaults to `noCommit`.
     */
    workspaceVaultSync?: DVaultSync;
    /**
     * Configuration for Random Note Lookup Command
     */
    randomNote?: LegacyRandomNoteConfig;
    /** Automatically fold frontmatter when opening a new note. False by default. */
    autoFoldFrontmatter?: boolean;
    /**
     * Configuration for Insert Note Index Command
     */
    insertNoteIndex?: LegacyInsertNoteIndexConfig;
    /** Notes that are too large can cause serious slowdowns for Sail. For
     * notes longer than this many characters, some features like backlinks will
     * be disabled to avoid slowdowns. Other functionality like note lookups will
     * continue to function.
     *
     * Defaults to 204800 characters, which is about 200 KiB.
     */
    maxNoteLength?: number;
    /**
     * Do not display the randomly generated colors for tags in the **editor**. Only
     * color tag links if it has been configured in the frontmatter. False by
     * default.
     */
    noRandomlyColoredTags?: boolean;
};
declare enum LegacyNoteAddBehavior {
    "childOfDomain" = "childOfDomain",
    "childOfDomainNamespace" = "childOfDomainNamespace",
    "childOfCurrent" = "childOfCurrent",
    "asOwnDomain" = "asOwnDomain"
}
declare enum LegacyLookupSelectionType {
    "selection2link" = "selection2link",
    "selectionExtract" = "selectionExtract",
    "none" = "none"
}
type LegacyNoteLookupConfig = {
    selectionType: LegacyLookupSelectionType;
    leaveTrace: boolean;
};
type LegacyLookupConfig = {
    note: LegacyNoteLookupConfig;
};
declare enum LegacyInsertNoteLinkAliasMode {
    "snippet" = "snippet",
    "selection" = "selection",
    "title" = "title",
    "prompt" = "prompt",
    "none" = "none"
}
type LegacyInsertNoteLinkConfig = {
    aliasMode: LegacyInsertNoteLinkAliasMode;
    multiSelect: boolean;
};
type LegacyJournalConfig = {
    dailyDomain: string;
    /**
     * If set, add all daily journals to specified vault
     */
    dailyVault?: string;
    name: string;
    dateFormat: string;
    addBehavior: LegacyNoteAddBehavior;
    /** 0 is Sunday, 1 is Monday, ... */
    firstDayOfWeek: number;
};
type LegacyScratchConfig = Pick<LegacyJournalConfig, "name" | "dateFormat" | "addBehavior">;
type LegacyRandomNoteConfig = {
    /**
     * Hiearchies to include
     */
    include?: string[];
    /**
     * Hiearchies to exclude
     */
    exclude?: string[];
};
type LegacyInsertNoteIndexConfig = {
    /**
     * Include marker when inserting note index.
     */
    marker?: boolean;
};
type SailSiteConfig = {
    /**
     * If set, add prefix to all asset links
     */
    assetsPrefix?: string;
    /**
     * Use this as root for creating canonical url for sites
     */
    canonicalBaseUrl?: string;
    /**
     * Copy assets from vault to site.
     * Default: true
     */
    copyAssets?: boolean;
    /**
     * If set, path to a custom header to include in published sites
     */
    customHeaderPath?: string;
    /**
     * If set, use google analytics to track users
     */
    ga_tracking?: string;
    /**
     * Path to favicon. Relative to workspace.
     * Default: "favicon.ico"
     */
    siteFaviconPath?: string;
    /**
     * Path to site logo
     */
    logo?: string;
    /**
     * By default, the domain of your `siteHierarchies` page
     */
    siteIndex?: string;
    /**
     * Hierarchies to publish
     */
    siteHierarchies: string[];
    /**
     * If true, show a last modified on the site
     */
    siteLastModified?: boolean;
    /**
     * Where your site will be published.
     * Relative to Sail workspace
     */
    siteRootDir: string;
    /**
     * Location of the github repo where your site notes are located.
     * By default, this is assumed to be your `workspaceRoot` if not set.
     */
    siteRepoDir?: string;
    /**
     * Folder where your notes will be kept. By default, "notes"
     * @deprecated: no longer used in 11ty
     */
    siteNotesDir?: string;
    /**
     * Url of site without trailing slash
     * eg. sail.so
     */
    siteUrl?: string;
    /**
     * Cname used for github pages
     * - default: none
     */
    githubCname?: string;
    /**
     * If set, add edit on github to this site"
     */
    gh_edit_link?: string;
    gh_edit_link_text?: string;
    gh_edit_branch?: string;
    gh_edit_view_mode?: "tree" | "edit";
    gh_edit_repository?: string;
    /**
     * Pretty refs help you identify when content is embedded from
     * elsewhere and provide links back to the source
     */
    usePrettyRefs?: boolean;
    /** @deprecated anchors are now always "hidden, but reveal on mouseover" in published sites. */
    hideBlockAnchors?: boolean;
    /** Whether frontmatter tags should be rendered in published websites. Defaults to true. */
    showFrontMatterTags?: boolean;
    /**
     * Do not display the randomly generated colors for tags. Only color tag links
     * if it has been configured in the frontmatter. False by default.
     */
    noRandomlyColoredTags?: boolean;
    /**
     * Control publication on a per hierarchy basis
     */
    config?: {
        [key: string]: LegacyHierarchyConfig;
    };
    /**
     * When publishing in multi-vault scenario,
     * how to handle duplicate notes
     */
    duplicateNoteBehavior?: LegacyDuplicateNoteBehavior;
    /**
     * When publishing, should stubs be written to disk?
     * Default: true
     * NOTE: if this isn't set to true, will cause
     * stub notes to be published with different ids each time
     */
    writeStubs?: boolean;
    /**
     * SEO related values
     */
    title?: string;
    description?: string;
    author?: string;
    twitter?: string;
    /** Default SEO image for published pages */
    image?: {
        url: string;
        alt: string;
    };
    /**
     * Use {@link https://github.com/Nevenall/remark-containers} in published site
     */
    useContainers?: boolean;
    /**
     * Generate changelog for published site
     * Default: false
     */
    generateChangelog?: boolean;
    /**
     * Set alternate port for preview
     * Default: 8080
     */
    previewPort?: boolean;
    /**
     * If set, value of your segment key
     */
    segmentKey?: string;
    /**
     * Required for auth
     */
    cognitoUserPoolId?: string;
    cognitoClientId?: string;
    /**
     * notes are published without the .html file extension
     */
    usePrettyLinks?: boolean;
    /** Display a `#` symbol in front of frontmatter tags in the tags listing. False by default. */
    useHashesForFMTags?: boolean;
};
type LegacySailGraphConfig = {
    zoomSpeed: number;
};
type LegacyHierarchyConfig = {
    publishByDefault?: boolean | {
        [key: string]: boolean;
    };
    noindexByDefault?: boolean;
    customFrontmatter?: LegacyCustomFMEntry[];
};
type LegacyCustomFMEntry = {
    key: string;
    value: any;
};
declare enum LegacyDuplicateNoteAction {
    USE_VAULT = "useVault"
}
type LegacyUseVaultBehaviorPayload = {
    vault: DVault;
} | string[];
type LegacyUseVaultBehavior = {
    action: LegacyDuplicateNoteAction;
    payload: LegacyUseVaultBehaviorPayload;
};
type LegacyDuplicateNoteBehavior = LegacyUseVaultBehavior;
type IntermediateNewConfig = Partial<Pick<SailConfig, "commands" | "workspace" | "preview" | "publishing">>;
type IntermediateOldConfig = Partial<SailConfigV4> & Required<Pick<SailConfigV4, "version">>;
type StrictConfigV4 = IntermediateOldConfig & IntermediateNewConfig & Required<Pick<IntermediateNewConfig, "commands" | "workspace" | "preview">> & Required<Pick<IntermediateOldConfig, "site">> & {
    version: 4;
};
export declare class DConfigLegacy {
    static configIsV4(config: any): config is StrictConfigV4;
    static v4ToV5(config: StrictConfigV4): SailConfig;
}
export {};
