/**
 * Simple utility class for generating labels with a time constrained _highlight_
 * Use it to give a certain label that is exposed in the UI some highlighting text
 * for a short amount of time.
 *
 * TODO: Depending on the usage, make this a service that can be
 * generally used to provide all public facing UI text
 * TODO: Make this a central place to manage all labels and their durations
 * TODO: Consolidate all constants defined across our codebase here.
 */
export declare class LabelUtils {
    static createLabelWithHighlight(opts: {
        value: string;
        highlight: {
            value: string;
            location: "prefix" | "suffix";
            expirationDate: Date;
        };
    }): string;
}
