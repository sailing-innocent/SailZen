import { URI } from "vscode-uri";
import { InvalidFilenameReason } from "./constants";
import { DEngineClient, DNodeOpts, DNodeProps, DNodePropsQuickInput, DNoteLoc, NoteChangeEntry, NoteDicts, NoteLocalConfig, NoteOpts, NoteProps, NotePropsByIdDict, NotePropsMeta, ReducedNoteQuickInput, ReducedDEngine, RespV3, SchemaModuleDict, SchemaModuleOpts, SchemaModuleProps, SchemaOpts, SchemaProps, SchemaPropsDict, SchemaRaw } from "./types";
import { DVault } from "./types/DVault";
export type ValidateFnameResp = {
    isValid: false;
    reason: InvalidFilenameReason;
} | {
    isValid: true;
    reason?: never;
};
/**
 * Utilities for dealing with nodes
 */
export declare class DNodeUtils {
    static addChild(parent: NotePropsMeta, child: NotePropsMeta): void;
    static removeChild(parent: NotePropsMeta, child: NotePropsMeta): void;
    static create(opts: DNodeOpts): DNodeProps;
    static basename(nodePath: string, rmExtension?: boolean): string;
    static dirName(nodePath: string): string;
    static domainName(nodePath: string): string;
    static fname(nodePath: string): string;
    static enhancePropForQuickInput({ props, schema, vaults, wsRoot, }: {
        props: DNodeProps;
        schema?: SchemaModuleProps;
        vaults: DVault[];
        wsRoot: string;
    }): DNodePropsQuickInput;
    static enhancePropForQuickInputV3(opts: {
        props: DNodeProps;
        vaults: DVault[];
        wsRoot: string;
        schema?: SchemaModuleProps;
        alwaysShow?: boolean;
    }): DNodePropsQuickInput;
    /**
     * This version skips unnecessary parameters such as wsRoot and vaults to
     * simplify the ILookupProvider interface
     * @param opts
     * @returns
     */
    static enhancePropForQuickInputV4(opts: {
        props: NoteProps;
        schema?: SchemaModuleProps;
        alwaysShow?: boolean;
    }): ReducedNoteQuickInput;
    static findClosestParent(fpath: string, noteDicts: NoteDicts, opts: {
        noStubs?: boolean;
        vault: DVault;
    }): NoteProps;
    static findClosestParentWithEngine(fpath: string, engine: ReducedDEngine, opts: {
        excludeStub?: boolean;
        vault: DVault;
    }): Promise<NotePropsMeta>;
    /**
     * Custom props are anything that is not a reserved key in Sail
     * @param props
     * @returns
     */
    static getCustomProps(props: any): any;
    static getDepth(node: DNodeProps): number;
    static getFNameDepth(fname: string): number;
    static getFullPath(opts: {
        wsRoot: string;
        vault: DVault;
        basename: string;
    }): string;
    static isRoot(note: NotePropsMeta): boolean;
    /**
     * Given a note, return the leaf name
     * @param note DNodeProps
     * @returns name of leaf node
     */
    static getLeafName(note: NotePropsMeta): string | undefined;
}
export declare class NoteUtils {
    /** Regular expression FrontMatter */
    static RE_FM: RegExp;
    /** Regular expression FrontMatter updated. */
    static RE_FM_UPDATED: RegExp;
    /** Regular expression FrontMatter created. */
    static RE_FM_CREATED: RegExp;
    /** Regular expression FrontMatter updated or created.  */
    static RE_FM_UPDATED_OR_CREATED: RegExp;
    static getNoteTraits(note: NotePropsMeta): string[];
    /**
     * Add node to parents up the note tree, or create stubs if no direct parents exists
     *
     * @param opts
     * @returns All parent notes that were changed
     */
    static addOrUpdateParents(opts: {
        note: NoteProps;
        noteDicts: NoteDicts;
        createStubs: boolean;
    }): NoteChangeEntry[];
    static addSchema(opts: {
        note: NoteProps;
        schemaModule: SchemaModuleProps;
        schema: SchemaProps;
    }): void;
    static create(opts: NoteOpts): NoteProps;
    static createWithSchema({ noteOpts, engine, }: {
        noteOpts: NoteOpts;
        engine: DEngineClient;
    }): Promise<NoteProps>;
    /**
     * Given a stub note, update it so that it has a schema applied to it
     * This is done before the stub note is accepted as a new item
     * and saved to the store
     */
    static updateStubWithSchema(opts: {
        stubNote: NoteProps;
        engine: DEngineClient;
    }): Promise<NoteProps>;
    static createRoot(opts: Partial<NoteOpts> & {
        vault: DVault;
    }): NoteProps;
    /**
     * Create stubs and add notes to parent
     * @param from
     * @param to
     */
    static createStubs(from: NoteProps, to: NoteProps): NoteProps[];
    /**
     * Create a wiki link to the given note
     *
     * @returns
     */
    static createWikiLink(opts: {
        note: NotePropsMeta;
        anchor?: {
            value: string;
            type: "header" | "blockAnchor";
        };
        alias?: {
            mode: "snippet" | "title" | "value" | "none";
            value?: string;
            tabStopIndex?: number;
        };
        useVaultPrefix?: boolean;
    }): string;
    static fromSchema({ fname, schemaModule, schemaId, vault, }: {
        fname: string;
        schemaModule: SchemaModuleProps;
        schemaId: string;
        vault: DVault;
    }): NoteProps;
    static genSchemaDesc(note: NoteProps, schemaMod?: SchemaModuleProps): string;
    static genJournalNoteTitle(opts: {
        fname: string;
        journalName: string;
    }): string;
    static updateNoteLocalConfig<K extends keyof NoteLocalConfig>(note: NoteProps, key: K, config: Partial<NoteLocalConfig[K]>): NoteProps;
    static genTitle(fname: string): string;
    static genTitleFromFullFname(fname: string): string;
    static getNotesWithLinkTo({ note, notes, }: {
        note: NotePropsMeta;
        notes: NotePropsMeta[];
    }): NotePropsMeta[];
    static getFullPath({ note, wsRoot, }: {
        note: NotePropsMeta;
        wsRoot: string;
    }): string;
    static getURI({ note, wsRoot, }: {
        note: NotePropsMeta;
        wsRoot: string;
    }): URI;
    /**
     * Get a list that has all the parents of the current note with the current note
     */
    static getNoteWithParents({ note, notes, sortDesc, }: {
        note: NoteProps;
        notes: NotePropsByIdDict;
        sortDesc?: boolean;
    }): NoteProps[];
    static getPathUpTo(hpath: string, numCompoenents: number): string;
    static getRoots(notes: NotePropsByIdDict): NoteProps[];
    /**
     * Add derived metadata from `noteHydrated` to `noteRaw`
     * By default, include the following properties:
     *  - parent
     *  - children
     * @param noteRaw - note for other fields
     * @param noteHydrated - note to get metadata properties from
     * @returns Merged Note object
     */
    static hydrate({ noteRaw, noteHydrated, opts, }: {
        noteRaw: NoteProps;
        noteHydrated: NotePropsMeta;
        opts?: Partial<{
            keepBackLinks: boolean;
        }>;
    }): {
        parent: import(".").DNodePointer | null;
        children: import(".").DNodePointer[];
        id: string;
        title: string;
        desc: string;
        updated: number;
        created: number;
        config?: NoteLocalConfig;
        fname: string;
        links: import(".").DLink[];
        anchors: {
            [index: string]: import(".").DNoteAnchorPositioned | undefined;
        };
        type: import(".").DNodeType;
        stub?: boolean;
        schemaStub?: boolean;
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
        image?: import(".").DNodeImage;
        traits?: string[];
    };
    static match({ notePath, pattern }: {
        notePath: string;
        pattern: string;
    }): boolean;
    static isDefaultTitle(props: NotePropsMeta): boolean;
    /**
     * Remove `.md` extension if exists and remove spaces
     * @param nodePath
     * @returns
     */
    static normalizeFname(nodePath: string): string;
    static isNoteProps(props: Partial<NoteProps>): props is NoteProps;
    static serializeExplicitProps(props: NoteProps): Partial<NoteProps>;
    static serialize(props: NoteProps, opts?: {
        excludeStub?: boolean;
    }): string;
    static toLogObj(note: NotePropsMeta): {
        fname: string;
        id: string;
        children: string[];
        vault: DVault;
        parent: string | null;
    };
    static toNoteLoc(note: NotePropsMeta): DNoteLoc;
    /**
     * Human readable note location. eg: `sail://foo (uisdfsdfsdf)`
     */
    static toNoteLocString(note: NotePropsMeta): string;
    static uri2Fname(uri: URI): string;
    /**
     * Check if input is a valid note
     * @param maybeNoteProps
     * @returns
     */
    static validate(maybeNoteProps: any): RespV3<boolean>;
    /**
     * Given a filename, return the validity of the filename.
     * If invalid, a reason string is also returned.
     * Only the first encountered reason will be reported.
     * @param fname filename
     * @returns boolean value representing the validity of the filename, and the reason if invalid
     */
    static validateFname(fname: string): ValidateFnameResp;
    /**
     * Given a file name, clean it so that it is valid
     * as per {@link NoteUtils.validateFname}
     * Optionally pass in the replace string that is used to replace
     * the illegal characters
     */
    static cleanFname(opts: {
        fname: string;
        replaceWith?: string;
    }): string;
    /** Generate a random color for `note`, but allow the user to override that color selection.
     *
     * @param fname The fname of note that you want to get the color of.
     * @returns The color, and whether this color was randomly generated or explicitly defined.
     */
    static color(opts: {
        fname: string;
        vault?: DVault;
        note?: NotePropsMeta;
    }): {
        color: string;
        type: "configured" | "generated";
    };
    /** Get the ancestors of a note, in the order of the closest to farthest.
     *
     * This function will continue searching for ancestors even if a note with `fname`
     * doesn't exist, provided that it has ancestors.
     * For example, if fname is `foo.bar.baz` but only `foo` exists, this function
     * will find `foo`.
     *
     * ```ts
     * const ancestorNotes = NoteUtils.ancestors({ fname });
     * for (const ancestor of ancestorNotes) { }
     * // or
     * const allAncestors = [...ancestorNotes];
     * ```
     *
     * @param opts.fname The fname of the note you are trying to get the ancestors of.
     * @param opts.vault The vault to look for. If provided, only notes from this vault will be included.
     * @param opts.engine The engine.
     * @param opts.includeSelf: If true, note with `fname` itself will be included in the ancestors.
     * @param opts.nonStubOnly: If true, only notes that are not stubs will be included.
     */
    static ancestors(opts: {
        fname: string;
        vault?: DVault;
        engine: DEngineClient;
        includeSelf?: boolean;
        nonStubOnly?: boolean;
    }): Promise<NotePropsMeta | undefined>;
    static isNote(uri: URI): boolean;
    static FILE_ID_PREFIX: string;
    /** This should be only used for files not in Sail workspace, for example a markdown file that's not in any vault. */
    static genIdForFile({ filePath, wsRoot, }: {
        filePath: string;
        wsRoot: string;
    }): string;
    /** Returns true if this is a note id generated by {@link NoteUtils.genIdForFile} */
    static isFileId(id: string): boolean;
    /** This should be only used for files not in Sail workspace, for example a markdown file that's not in any vault. */
    static createForFile(opts: {
        filePath: string;
        contents: string;
        wsRoot: string;
    }): NoteProps;
    static FAKE_ID_PREFIX: string;
    /** Create a fake note object for something that is not actually a note in the workspace.
     *
     * For example when we need to render a piece of an actual note. If you need
     * to create a fake note for an actual file, prefer
     * {@link NoteUtils.createForFile} instead.
     */
    static createForFake(opts: {
        contents: string;
        fname: string;
        id: string;
        vault: DVault;
    }): NoteProps;
}
type SchemaMatchResult = {
    schemaModule: SchemaModuleProps;
    schema: SchemaProps;
    namespace: boolean;
    notePath: string;
};
export declare class SchemaUtils {
    static createFromSchemaRaw(opts: SchemaRaw & {
        vault: DVault;
    }): SchemaProps;
    static createFromSchemaOpts(opts: SchemaOpts & {
        vault: DVault;
    }): SchemaProps;
    private static processUntypedTemplate;
    static createModule(opts: SchemaModuleOpts): SchemaModuleOpts;
    static createModuleProps(opts: {
        fname: string;
        vault: DVault;
    }): SchemaModuleProps;
    static createRootModule(opts: Partial<SchemaProps> & {
        vault: DVault;
    }): SchemaModuleOpts;
    static createRootModuleProps(fname: string, vault: DVault, opts?: Partial<SchemaProps>): SchemaModuleProps;
    static enhanceForQuickInput({ props, vaults, }: {
        props: SchemaModuleProps;
        vaults: DVault[];
    }): DNodePropsQuickInput;
    static getModuleRoot(module: SchemaModuleOpts | SchemaModuleProps): SchemaProps;
    /**
     * If no pattern field, get the id.
     * If pattern field, check if namespace and translate into glob pattern
     * @param schema
     * @param opts
     * @returns
     */
    static getPattern: (schema: SchemaProps, opts?: {
        isNotNamespace?: boolean;
    }) => string;
    /**
     * Get full pattern starting from the root
     * @param schema
     * @param schemas
     * @returns
     */
    static getPatternRecursive: (schema: SchemaProps, schemas: SchemaPropsDict) => string;
    /**
     * @param param0
     * @returns
     */
    static getPath({ root, fname }: {
        root: string;
        fname: string;
    }): string;
    static doesSchemaExist({ id, engine, }: {
        id: string;
        engine: DEngineClient;
    }): Promise<boolean>;
    static getSchemaFromNote({ note, engine, }: {
        note: NoteProps;
        engine: DEngineClient;
    }): Promise<SchemaModuleProps | undefined>;
    static hasSimplePattern: (schema: SchemaProps, opts?: {
        isNotNamespace?: boolean;
    }) => boolean;
    /**
     * Match and assign schemas to all nodes within a domain. Note - only use this
     * during engine init where SchemaModuleDict is available.
     *
     * @param domain
     * @param notes
     * @param schemas
     */
    static matchDomain(domain: NoteProps, notes: NotePropsByIdDict, schemas: SchemaModuleDict): void;
    static matchDomainWithSchema(opts: {
        noteCandidates: NoteProps[];
        notes: NotePropsByIdDict;
        schemaCandidates: SchemaProps[];
        schemaModule: SchemaModuleProps;
        matchNamespace?: boolean;
    }): void;
    static matchPath(opts: {
        notePath: string;
        engine: DEngineClient;
    }): Promise<SchemaMatchResult | undefined>;
    /**
     * Find proper schema from schema module that can be applied to note
     */
    static findSchemaFromModule(opts: {
        notePath: string;
        schemaModule: SchemaModuleProps;
    }): SchemaMatchResult | undefined;
    /**
     *
     * @param param0
     * @return
     *  - schemaModule
     *  - schema
     *  - namespace
     *  - notePath
     */
    static matchPathWithSchema({ notePath, matched, schemaCandidates, schemaModule, matchNamespace, }: {
        notePath: string;
        matched: string;
        schemaCandidates: SchemaProps[];
        schemaModule: SchemaModuleProps;
        matchNamespace?: boolean;
    }): SchemaMatchResult | undefined;
    static matchNotePathWithSchemaAtLevel({ notePath, schemas, schemaModule, matchNamespace, }: {
        notePath: string;
        schemas: SchemaProps[];
        schemaModule: SchemaModuleProps;
        matchNamespace?: boolean;
    }): SchemaMatchResult | undefined;
    static serializeSchemaProps(props: SchemaProps | SchemaOpts): SchemaRaw;
    static isSchemaUri(uri: URI): boolean;
    static serializeModuleProps(moduleProps: SchemaModuleProps): string;
}
export {};
