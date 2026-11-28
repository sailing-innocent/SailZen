import { SchemaData, SchemaTemplate } from "./types";
export type SchemaInMaking = {
    id?: string;
    title?: string;
    parent?: string;
    pattern?: string;
    template?: SchemaTemplate;
    children?: SchemaInMaking[];
    desc?: string;
};
export type SchemaToken = Required<Pick<SchemaData, "pattern">> & Pick<SchemaData, "template"> & Pick<SchemaData, "desc">;
/**
 * Utils for generating a Schema **JSON** file.  For working with Schema
 * objects, see SchemaUtils.
 */
export declare class SchemaCreationUtils {
    static getBodyForTokenizedMatrix({ topLevel, tokenizedMatrix, }: {
        topLevel: SchemaInMaking;
        tokenizedMatrix: SchemaToken[][];
    }): string;
}
