import { NotePropsByIdDict, NotePropsMeta } from "@saili/common-all";
export declare class HierarchyUtils {
    /**
     * Get children of current note
     * @param opts.skipLevels: how many levels to skip for child
     * @returns
     */
    static getChildren: (opts: {
        skipLevels: number;
        note: NotePropsMeta;
        notes: NotePropsByIdDict;
    }) => import("@saili/common-all").NoteProps[];
}
