import { SailConfig, DuplicateNoteBehavior, DVault, HierarchyConfig, NotePropsByIdDict, NoteProps, SailPublishingConfig, ISailError, NotePropsMeta } from "@saili/common-all";
import { DEngineClient } from "../types";
/**
 * @deprecated - prefer to use methods in unified/SiteUtils if they exist.
 */
export declare class SiteUtils {
    static canPublish(opts: {
        note: NotePropsMeta;
        config: SailConfig;
        engine: DEngineClient;
    }): boolean;
    static isPublished(opts: {
        note: NoteProps;
        config: SailConfig;
        engine: DEngineClient;
    }): boolean;
    static copyAssets(opts: {
        wsRoot: string;
        vault: DVault;
        siteAssetsDir: string;
        /**
         * Delete existing siteAssets
         */
        deleteSiteAssetsDir?: boolean;
    }): Promise<void>;
    /**
     * Creates a placeholder note that can be used for rendering a 403 error
     * message.
     */
    static create403StaticNote(opts: {
        engine: DEngineClient;
    }): NoteProps;
    static createSiteOnlyNotes(opts: {
        engine: DEngineClient;
    }): NoteProps[];
    static filterByConfig(opts: {
        engine: DEngineClient;
        config: SailConfig;
        noExpandSingleDomain?: boolean;
    }): Promise<{
        notes: NotePropsByIdDict;
        domains: NoteProps[];
    }>;
    /**
     * Filter notes to be published using hierarchy
     */
    static filterByHierarchy(opts: {
        domain: string;
        config: SailConfig;
        engine: DEngineClient;
        navOrder: number;
    }): Promise<{
        notes: NotePropsByIdDict;
        domain: NoteProps;
    } | undefined>;
    /**
     * Apply custom frontmatter and formatting to note
     */
    static cleanNote({ note, hConfig, }: {
        note: NoteProps;
        hConfig: HierarchyConfig;
    }): {
        body: string;
        id: string;
        title: string;
        desc: string;
        updated: number;
        created: number;
        config?: import("@saili/common-all").NoteLocalConfig;
        fname: string;
        links: import("@saili/common-all").DLink[];
        anchors: {
            [index: string]: import("@saili/common-all").DNoteAnchorPositioned | undefined;
        };
        type: import("@saili/common-all").DNodeType;
        stub?: boolean;
        schemaStub?: boolean;
        parent: import("@saili/common-all").DNodePointer | null;
        children: import("@saili/common-all").DNodePointer[];
        data: any;
        custom?: any;
        schema?: {
            moduleId: string;
            schemaId: string;
        };
        vault: DVault;
        contentHash?: string;
        color?: string;
        tags?: string | string[];
        image?: import("@saili/common-all").DNodeImage;
        traits?: string[];
    };
    static getConfigForHierarchy(opts: {
        config: SailConfig;
        noteOrName: NotePropsMeta | string;
    }): HierarchyConfig;
    static getSiteOutputPath(opts: {
        config: SailConfig;
        wsRoot: string;
        stage: "dev" | "prod";
    }): string;
    static getSiteUrlRootForVault({ vault, config, }: {
        vault: DVault;
        config: SailConfig;
    }): {
        url?: string;
        index?: string;
    };
    static getSitePrefixForNote(config: SailConfig): string;
    static getSiteUrlPathForNote({ pathValue, pathAnchor, config, addPrefix, note, }: {
        pathValue?: string;
        pathAnchor?: string;
        config: SailConfig;
        addPrefix?: boolean;
        note?: NoteProps;
    }): string;
    static handleDup(opts: {
        dupBehavior?: DuplicateNoteBehavior;
        allowStubs?: boolean;
        engine: DEngineClient;
        fname: string;
        config: SailConfig;
        noteCandidates: NoteProps[];
    }): Promise<NoteProps | undefined>;
    /**
     * Is the current note equivalent ot the index of the published site?
     * @returns
     */
    static isIndexNote({ indexNote, note, }: {
        indexNote?: string;
        note: NoteProps;
    }): boolean;
    static validateConfig(sconfig: SailPublishingConfig): {
        error?: ISailError;
    };
}
