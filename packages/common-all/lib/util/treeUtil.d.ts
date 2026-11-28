import { z } from "../parse";
import { NotePropsByIdDict, RespV3 } from "../types";
import type { Sidebar } from "../sidebar";
type TreeMenuNodeIcon = "numberOutlined" | "plusOutlined";
export type TreeMenuNode = {
    key: string;
    title: string;
    icon: TreeMenuNodeIcon | null;
    hasTitleNumberOutlined: boolean;
    vaultName: string;
    children?: TreeMenuNode[];
    contextValue?: string;
};
export declare const treeMenuSchema: z.ZodObject<{
    roots: z.ZodArray<z.ZodType<TreeMenuNode, unknown, z.core.$ZodTypeInternals<TreeMenuNode, unknown>>>;
    child2parent: z.ZodRecord<z.ZodString, z.ZodNullable<z.ZodString>>;
    notesLabelById: z.ZodOptional<z.ZodRecord<z.ZodString, z.ZodString>>;
}, z.core.$strip>;
export type TreeMenu = z.infer<typeof treeMenuSchema>;
export declare enum TreeViewItemLabelTypeEnum {
    title = "title",
    filename = "filename"
}
export type TreeNode = {
    fname: string;
    children: TreeNode[];
};
export declare class TreeUtils {
    static generateTreeData(noteDict: NotePropsByIdDict, sidebar: Sidebar): TreeMenu;
    static getAllParents: ({ child2parent, noteId, }: {
        child2parent: {
            [key: string]: string | null;
        };
        noteId: string;
    }) => string[];
    /**
     * Create tree starting from given root note. Use note's children properties to define TreeNode children relationship
     *
     * @param allNotes
     * @param rootNoteId
     * @returns
     */
    static createTreeFromEngine(allNotes: NotePropsByIdDict, rootNoteId: string): TreeNode;
    /**
     * Create tree from list of file names. Use the delimiter "." to define TreeNode children relationship
     */
    static createTreeFromFileNames(fNames: string[], rootNote: string): {
        fname: string;
        children: TreeNode[];
    };
    /**
     * Check if two trees are equal.
     * Two trees are equal if and only if fnames are equal and children tree nodes are equal
     */
    static validateTreeNodes(expectedTree: TreeNode, actualTree: TreeNode): RespV3<void>;
}
export {};
