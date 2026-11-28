/** Object with responsibility to match strings with the given order. */
export declare class OrderedMatcher {
    private regexPattern;
    constructor(tokens: string[]);
    /** Checks whether the given strings matches all the tokens in order. */
    isMatch(str: string): RegExpMatchArray | null;
}
