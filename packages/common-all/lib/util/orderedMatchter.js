/** Object with responsibility to match strings with the given order. */
export class OrderedMatcher {
    regexPattern;
    constructor(tokens) {
        // https://regex101.com/r/eMTNJ0/1
        this.regexPattern = tokens.join(".*").toLowerCase();
    }
    /** Checks whether the given strings matches all the tokens in order. */
    isMatch(str) {
        const isMatch = str.toLowerCase().match(this.regexPattern);
        return isMatch;
    }
}
//# sourceMappingURL=orderedMatchter.js.map