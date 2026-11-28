import { DEngineClient, NoteProps, NotePropsByIdDict, ReducedDEngine } from "..";
export type TransformedQueryString = {
    /** Transformed query string value.   */
    queryString: string;
    /**
     * This will be set to true when the query string had wiki link decoration
     * (Eg. [[some.note]]) and that decoration has been stripped out to be able
     * to query for the content of the wiki link.
     * */
    wasMadeFromWikiLink: boolean;
    /**
     * We split by dots to allow for hierarchy matches that have the inside
     * part of the hierarchy omitted.
     *
     * For example if we have a query such as: `h1.h4` we want to match results
     * like `h1.h2.h3.h4` however FuseJS sees `h1.h4` as a single token hence
     * `h1.h2.h3.h4` won't be matched (without ramping up fuzz threshold)
     * So what we are going to to do is split `h1.h4` into `h1 h4` in our transformed
     * queryString for fuse JS to see `h1` and `h4` as two separate tokens.
     * With `h1` and `h4` seen as separate tokens FuseJS will also match out of order
     * notes such as `h4.h1` hence we keep this array to filter out results that
     * match the order.
     *
     * When we are splitting by dots we will only be performing the split on the first
     * part of the query string, to allow other tokens to be used with the split by dots
     * as example querying for 'h1.h4 hi' will match all the values that are within the
     * 'h1...h4...' hierarchy that also contain token 'hi'.
     * */
    splitByDots?: string[];
    /**
     * If there is clear vault name within the query will be set to such vault name
     * otherwise it will be undefined.
     * */
    vaultName?: string;
    /**
     * Set to true when we only want to match direct children of the hierarchy. */
    onlyDirectChildren?: boolean;
    /** Original query string value */
    originalQuery: string;
};
export declare class NoteLookupUtils {
    /**
     * Get qs for current level of the hierarchy
     * @param qs
     * @returns
     */
    static getQsForCurrentLevel: (qs: string) => string;
    static fetchRootResultsFromEngine: (engine: ReducedDEngine) => Promise<NoteProps[]>;
    static fetchRootResults: (notes: NotePropsByIdDict) => NoteProps[];
    /**
     * The core of Sail lookup logic
     */
    static lookup({ qsRaw, engine, showDirectChildrenOnly, }: {
        qsRaw: string;
        engine: DEngineClient;
        showDirectChildrenOnly?: boolean;
    }): Promise<NoteProps[]>;
    static slashToDot(ent: string): string;
    /**
     * Transform Sail lookup syntax to fusejs syntax
     * - if wiki string, strip out wiki links
     */
    static transformQueryString({ query, onlyDirectChildren, }: {
        query: string;
        onlyDirectChildren?: boolean | undefined;
    }): TransformedQueryString;
}
