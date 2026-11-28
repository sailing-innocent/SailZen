import _ from "lodash";
import { z } from "../parse";
import { SailError } from "../error";
import { TAGS_HIERARCHY, TAGS_HIERARCHY_BASE } from "../constants";
import { VaultUtils } from "../vault";
import { assertUnreachable } from "../error";
const treeMenuNodeSchema = z.lazy(() => z.object({
    key: z.string(),
    title: z.string(),
    icon: z
        .union([z.literal("numberOutlined"), z.literal("plusOutlined")])
        .nullable(),
    hasTitleNumberOutlined: z.boolean(),
    vaultName: z.string(),
    children: z.array(treeMenuNodeSchema),
    contextValue: z.string().optional(),
}));
export const treeMenuSchema = z.object({
    roots: z.array(treeMenuNodeSchema),
    child2parent: z.record(z.string(), z.string().nullable()),
    notesLabelById: z.record(z.string(), z.string()).optional(), // cheap acces to note labels when computing breadcrumps (TODO improve `TreeMenu` datastructure so that this field is not necessary)
});
export var TreeViewItemLabelTypeEnum;
(function (TreeViewItemLabelTypeEnum) {
    TreeViewItemLabelTypeEnum["title"] = "title";
    TreeViewItemLabelTypeEnum["filename"] = "filename";
})(TreeViewItemLabelTypeEnum || (TreeViewItemLabelTypeEnum = {}));
export class TreeUtils {
    static generateTreeData(noteDict, sidebar) {
        function itemToNoteId(item) {
            const { type } = item;
            switch (type) {
                case "category": {
                    return item.link?.id;
                }
                case "note": {
                    return item.id;
                }
                default:
                    assertUnreachable(type);
            }
        }
        function itemToTreeMenuNode(sidebarItem, opts) {
            const { child2parent, parent, notesLabelById } = opts;
            const noteId = itemToNoteId(sidebarItem);
            const note = noteDict[noteId]; // explicitly casting since `noUncheckedIndexedAccess` is currently not enabled
            if (_.isUndefined(note)) {
                return undefined;
            }
            let icon = null;
            if (note.fname.toLowerCase() === TAGS_HIERARCHY_BASE) {
                icon = "numberOutlined";
            }
            else if (note.stub) {
                icon = "plusOutlined";
            }
            const title = sidebarItem.label ?? note.title;
            notesLabelById[note.id] = title;
            const treeMenuNode = {
                key: note.id,
                title,
                icon,
                hasTitleNumberOutlined: note.fname.startsWith(TAGS_HIERARCHY),
                vaultName: VaultUtils.getName(note.vault),
                children: [],
            };
            if (child2parent[note.id] === undefined) {
                child2parent[note.id] = parent;
            }
            if (sidebarItem.type === "category") {
                treeMenuNode.children = sidebarItem.items
                    .map((item) => itemToTreeMenuNode(item, {
                    child2parent,
                    parent: note.id,
                    notesLabelById,
                }))
                    .filter((maybeTreeMenuNode) => Boolean(maybeTreeMenuNode));
            }
            return treeMenuNode;
        }
        const child2parent = {};
        const notesLabelById = {};
        const roots = sidebar
            .map((sidebarItem) => itemToTreeMenuNode(sidebarItem, {
            child2parent,
            parent: null,
            notesLabelById,
        }))
            .filter((maybeTreeMenuNode) => Boolean(maybeTreeMenuNode));
        return {
            roots,
            child2parent,
            notesLabelById,
        };
    }
    static getAllParents = ({ child2parent, noteId, }) => {
        const activeNoteIds = [];
        let parent = child2parent[noteId];
        while (parent) {
            activeNoteIds.unshift(parent);
            parent = child2parent[parent];
        }
        return activeNoteIds;
    };
    /**
     * Create tree starting from given root note. Use note's children properties to define TreeNode children relationship
     *
     * @param allNotes
     * @param rootNoteId
     * @returns
     */
    static createTreeFromEngine(allNotes, rootNoteId) {
        const note = allNotes[rootNoteId];
        if (note) {
            const children = note.children
                .filter((child) => child !== note.id)
                .sort((a, b) => a.localeCompare(b))
                .map((note) => this.createTreeFromEngine(allNotes, note));
            const fnames = note.fname.split(".");
            return { fname: fnames[fnames.length - 1], children };
        }
        else {
            throw new SailError({
                message: `No note found in engine for "${rootNoteId}"`,
            });
        }
    }
    /**
     * Create tree from list of file names. Use the delimiter "." to define TreeNode children relationship
     */
    static createTreeFromFileNames(fNames, rootNote) {
        const result = [];
        fNames.forEach((name) => {
            if (name !== rootNote) {
                name.split(".").reduce((object, fname) => {
                    let item = (object.children = object.children || []).find((q) => q.fname === fname);
                    if (!item) {
                        object.children.push((item = { fname, children: [] }));
                    }
                    return item;
                }, { children: result });
            }
        });
        return { fname: rootNote, children: result };
    }
    /**
     * Check if two trees are equal.
     * Two trees are equal if and only if fnames are equal and children tree nodes are equal
     */
    static validateTreeNodes(expectedTree, actualTree) {
        if (expectedTree.fname !== actualTree.fname) {
            return {
                error: new SailError({
                    message: `Fname differs. Expected: "${expectedTree.fname}". Actual "${actualTree.fname}"`,
                }),
            };
        }
        expectedTree.children.sort((a, b) => a.fname.localeCompare(b.fname));
        actualTree.children.sort((a, b) => a.fname.localeCompare(b.fname));
        if (expectedTree.children.length !== actualTree.children.length) {
            const expectedChildren = expectedTree.children.map((child) => child.fname);
            const actualChildren = actualTree.children.map((child) => child.fname);
            return {
                error: new SailError({
                    message: `Mismatch at ${expectedTree.fname}'s children. Expected: "${expectedChildren}". Actual "${actualChildren}"`,
                }),
            };
        }
        for (const [idx, value] of expectedTree.children.entries()) {
            const resp = this.validateTreeNodes(value, actualTree.children[idx]);
            if (resp.error) {
                return {
                    error: new SailError({
                        message: `Mismatch at ${expectedTree.fname}'s children. ${resp.error.message}.`,
                    }),
                };
            }
        }
        return { data: undefined };
    }
}
//# sourceMappingURL=treeUtil.js.map