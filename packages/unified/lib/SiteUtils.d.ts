import { SailPublishingConfig, DuplicateNoteBehavior, DVault, HierarchyConfig, ISailError, SailConfig, NoteDicts, NoteProps, NotePropsMeta } from "@saili/common-all";
export declare class SiteUtils {
    static canPublish(opts: {
        note: NoteProps;
        config: SailConfig;
        wsRoot: string;
        vaults: DVault[];
    }): boolean;
    static isPublished(opts: {
        note: NoteProps;
        config: SailConfig;
        wsRoot: string;
        vaults: DVault[];
    }): boolean;
    /**
     * Creates a placeholder note that can be used for rendering a 403 error
     * message.
     */
    static create403StaticNote(opts: {
        vaults: DVault[];
    }): NoteProps;
    static createSiteOnlyNotes(opts: {
        vaults: DVault[];
    }): NoteProps[];
    /**
     * Apply custom frontmatter and formatting to note
     */
    static cleanNote({ note, hConfig, }: {
        note: NoteProps;
        hConfig: HierarchyConfig;
    }): {
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
        body: string;
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
        noteOrName: NoteProps | string;
    }): HierarchyConfig;
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
        fname: string;
        config: SailConfig;
        noteCandidates: NoteProps[];
        noteDict: NoteDicts;
        vaults: DVault[];
        wsRoot: string;
    }): NoteProps | undefined;
    /**
     * Is the current note equivalent ot the index of the published site?
     * @returns
     */
    static isIndexNote({ indexNote, note, }: {
        indexNote?: string;
        note: NotePropsMeta;
    }): boolean;
    static validateConfig(sconfig: SailPublishingConfig): {
        error?: ISailError;
    };
}
