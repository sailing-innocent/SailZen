import { NotePropsByIdDict, NotePropsByFnameDict, NoteProps, NoteDicts, NotePropsMeta } from "./types";
import { DVault } from "./types/DVault";
/**
 * Utilities for working with NoteDicts. The reason NoteDicts is not a class is due to needing
 * to work with primitive objects with redux
 */
export declare class NoteDictsUtils {
    /**
     * Construct a full NoteDicts from a set of Note Props
     * @param notes
     */
    static createNoteDicts(notes: NoteProps[]): NoteDicts;
    /**
     * Construct NotePropsByIdDict from list of NoteProps
     *
     * @param notes Used to populate map
     * @returns NotePropsByIdDict
     */
    static createNotePropsByIdDict(notes: NoteProps[]): NotePropsByIdDict;
    /**
     * Find notes by fname. If vault is provided, filter results so that only notes with matching vault is returned
     * Return empty array if no match is found
     *
     * @param fname
     * @param noteDicts
     * @param vault If provided, use to filter results
     * @param skipCloneDeep If true, do not clone notes and return same reference in noteDicts.
     * This means that any changes to the returned notes will affect the same note in noteDicts
     * @returns Array of NoteProps matching opts
     */
    static findByFname({ fname, noteDicts, vault, skipCloneDeep, }: {
        fname: string;
        noteDicts: NoteDicts;
        vault?: DVault;
        skipCloneDeep?: boolean;
    }): NoteProps[];
    /**
     * Remove note from both notesById and notesByFname.
     * Returns true if note was deleted from both. False otherwise
     *
     * @param note note to delete
     * @param noteDicts
     * @return whether note was deleted
     */
    static delete(note: NoteProps, noteDicts: NoteDicts): boolean;
    /**
     * Add note to notesById and notesByFname.
     * If note id already exists, check to see if it corresponds to same note by fname.
     * If fname match, then we only need to update notesById. If fname doesn't match, remove old id from notesByFname first before updating both.
     *
     * Otherwise, if note id doesn't exist, add to both dictionaries
     *
     * @param note to add
     * @returns
     */
    static add(note: NoteProps, noteDicts: NoteDicts): void;
}
/**
 * Utilities for working with NotePropsByFnameDict.
 */
export declare class NoteFnameDictUtils {
    /**
     * Use NotePropsByIdDict to create a inverted index of {key -> value} where key = noteFname and value is list of ids corresponding to that fname
     *
     * @param notesById Used to populate map
     * @returns
     */
    static createNotePropsByFnameDict(notesById: NotePropsByIdDict): NotePropsByFnameDict;
    /**
     * Add note to notesByFname dictionary. If note fname exists, add note id to existing list of ids
     *
     * @param note to add
     * @param notesByFname dictionary to modify
     */
    static add(note: NotePropsMeta, notesByFname: NotePropsByFnameDict): void;
    /**
     * Delete note from notesByFname dictionary. If note exists and it corresponds to last entry for that fname, delete fname entry
     * from dictionary as well
     * Returns true if note was deleted
     *
     * @param note to delete
     * @param notesByFname dictionary to modify
     * @returns whether note was deleted
     */
    static delete(note: NotePropsMeta, notesByFname: NotePropsByFnameDict): boolean;
    /**
     * Merge two NotePropsByFnameDict into a single NotePropsByFnameDict
     * If key exists in both, merge values into a single array
     *
     * @return new merged NotePropsByFnameDict without modifying existing NotePropsByFnameDicts
     */
    static merge(fnameDictOne: NotePropsByFnameDict, fnameDictTwo: NotePropsByFnameDict): NotePropsByFnameDict;
}
