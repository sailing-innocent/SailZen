import { NoteProps } from "@saili/common-all";
export declare class InMemoryNoteCache {
    /** Note map which maps lowercase file name to a list {@link NoteProps}
     *  that have the matching file name.
     *
     *  Primary reason file name maps to a list of notes is having notes with
     *  the same file name in different vaults.
     *  */
    private readonly mapFNameToNotes;
    constructor(notes: NoteProps[]);
    private static initializeFileNameMap;
    /** Returns list of {@link NoteProps} that have matching file name (ignoring
     *  the file name case). Will return empty list if no notes match.  */
    getNotesByFileNameIgnoreCase(fileName: string): NoteProps[];
}
