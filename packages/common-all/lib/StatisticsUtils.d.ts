/**
 * Utility class for _very simple_ statistics operations.
 * When we need to do complex and/or expensive stats,
 * consider introducing a dedicated stats library.
 *
 * This is here to use until that point comes
 */
import { NoteProps } from ".";
export type NonEmptyArray<T> = [T, ...T[]];
export declare class StatisticsUtils {
    static isNonEmptyArray<T>(arr: T[]): arr is NonEmptyArray<T>;
    static getBasicStats(arr: NonEmptyArray<number>): {
        mean: number;
        median: number;
        stddev: number;
        max: number;
    };
    /**
     * Get standard deviation from array of numbers.
     */
    static stddev(arr: NonEmptyArray<number>): number;
    /**
     * Get median value from array of numbers.
     */
    static median(arr: NonEmptyArray<number>): number;
    /**
     * Convenience command to grab a collection of statistics from a set of notes.
     *
     * Given an array of notes, aggregate and get basic statistics of the following:
     *
     * number of children,
     * number of links,
     * number of characters in body,
     * note depth
     *
     * This is used to grab statistics about quantifiable properties from a set of notes
     * for analytics purposes.
     *
     * @param notes Notes to get basic stats from
     * @returns an object holding all basic stats
     */
    static getBasicStatsFromNotes(notes: NoteProps[]): {
        numChildren: number;
        numLinks: number;
        numChars: number;
        noteDepth: number;
        maxNumChildren: number;
        medianNumChildren: number;
        stddevNumChildren: number;
        maxNumLinks: number;
        medianNumLinks: number;
        stddevNumLinks: number;
        maxNumChars: number;
        medianNumChars: number;
        stddevNumChars: number;
        maxNoteDepth: number;
        medianNoteDepth: number;
        stddevNoteDepth: number;
    } | undefined;
}
