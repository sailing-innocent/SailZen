/**
 * Returns levenshtein distance between the two strings, the higher the number
 * the further apart the strings are. 0 signals that the strings are equal. */
export declare function levenshteinDistance(s1: string, s2: string): number;
export declare function parseSailURI(linkString: string): {
    link: string;
    vaultName?: undefined;
} | {
    vaultName: string;
    link: string;
};
