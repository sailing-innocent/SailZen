import { DStore, DVault, SchemaModuleOpts, SchemaModuleProps, SchemaOpts, SchemaProps } from "@saili/common-all";
export declare class ParserBaseV2 {
    opts: {
        store: DStore;
        logger: any;
    };
    constructor(opts: {
        store: DStore;
        logger: any;
    });
    get logger(): any;
}
export declare class SchemaParserV2 extends ParserBaseV2 {
    static parseRaw(schemaOpts: SchemaModuleOpts, opts: {
        root: DVault;
        fname: string;
        wsRoot: string;
    }): Promise<SchemaModuleProps>;
    private static noInlineChildren;
    static validateTopSchemasHaveIds(schemas: SchemaOpts[]): void;
    private static getSchemasFromFile;
    static createFromSchemaRaw(opts: SchemaOpts & {
        vault: DVault;
    }): SchemaProps;
    static createFromSchemaOpts(opts: SchemaOpts & {
        vault: DVault;
    }): SchemaProps;
    private static validateSchemaOptsPreCreation;
    private static processChildren;
    /**
     * Ids are optional for inline schemas hence if there isn't an id
     * we will generate the identifier. */
    private static setIdIfMissing;
    static parseSchemaModuleOpts(schemaModuleProps: SchemaModuleOpts, opts: {
        fname: string;
        root: DVault;
        wsRoot: string;
    }): Promise<SchemaModuleProps>;
}
export declare function file2Schema(fpath: string, wsRoot: string): Promise<SchemaModuleProps>;
export declare function string2Schema({ vault, content, fname, wsRoot, }: {
    vault: DVault;
    content: string;
    fname: string;
    wsRoot: string;
}): Promise<SchemaModuleProps>;
