import _ from "lodash";
import { FuseExtendedSearchConstants, NoteUtils, } from "..";
const PAGINATE_LIMIT = 50;
export class NoteLookupUtils {
    /**
     * Get qs for current level of the hierarchy
     * @param qs
     * @returns
     */
    static getQsForCurrentLevel = (qs) => {
        const lastDotIndex = qs.lastIndexOf(".");
        return lastDotIndex < 0 ? "" : qs.slice(0, lastDotIndex + 1);
    };
    static fetchRootResultsFromEngine = async (engine) => {
        // TODO: Support findNotesMeta
        const roots = await engine.findNotes({ fname: "root" });
        const childrenOfRoot = roots.flatMap((ent) => ent.children);
        const childrenOfRootNotes = await engine.bulkGetNotes(childrenOfRoot);
        return roots.concat(childrenOfRootNotes.data);
    };
    static fetchRootResults = (notes) => {
        const roots = NoteUtils.getRoots(notes);
        const childrenOfRoot = roots.flatMap((ent) => ent.children);
        const childrenOfRootNotes = _.map(childrenOfRoot, (ent) => notes[ent]);
        return roots.concat(childrenOfRootNotes);
    };
    /**
     * The core of Sail lookup logic
     */
    static async lookup({ qsRaw, engine, showDirectChildrenOnly, }) {
        const qsClean = this.slashToDot(qsRaw);
        // special case: if query is empty, fetch top level notes
        if (_.isEmpty(qsClean)) {
            return NoteLookupUtils.fetchRootResultsFromEngine(engine);
        }
        // otherwise, query engine for results
        const transformedQuery = NoteLookupUtils.transformQueryString({
            query: qsRaw,
            onlyDirectChildren: showDirectChildrenOnly,
        });
        let nodes = await engine.queryNotes({
            qs: transformedQuery.queryString,
            originalQS: qsRaw,
            onlyDirectChildren: showDirectChildrenOnly,
        });
        // limit number of results. currently, this is hardcoded and we don't paginate
        // this is okay because we rely on user refining query to get more results
        if (!nodes) {
            return [];
        }
        if (nodes.length > PAGINATE_LIMIT) {
            nodes = nodes.slice(0, PAGINATE_LIMIT);
        }
        return nodes;
    }
    static slashToDot(ent) {
        return ent.replace(/\//g, ".");
    }
    /**
     * Transform Sail lookup syntax to fusejs syntax
     * - if wiki string, strip out wiki links
     */
    static transformQueryString({ query, onlyDirectChildren, }) {
        const trimmed = query.trim();
        // Detect wiki link decoration and apply wiki link processing
        if (trimmed.startsWith("[[") && trimmed.endsWith("]]")) {
            return wikiTransform(trimmed);
        }
        else {
            return regularTransform(trimmed, onlyDirectChildren);
        }
    }
}
function wikiTransform(trimmedQuery) {
    let vaultName;
    // Remove the '[[' ']]' decoration.
    let transformed = trimmedQuery.slice(2, -2);
    // Process description such as [[some description|some.note]]
    if (transformed.includes("|")) {
        transformed = transformed.slice(transformed.indexOf("|") + 1);
    }
    // Process header value. For now we will remove the header since its
    // not yet indexed within our look up engine.
    if (transformed.includes("#")) {
        transformed = transformed.slice(0, transformed.indexOf("#"));
    }
    if (transformed.includes("sail://")) {
        // https://regex101.com/r/ICcyK6/1/
        vaultName = transformed.match(/sail:\/\/(.*?)\//)?.[1];
        transformed = transformed.slice(transformed.lastIndexOf("/") + 1);
    }
    console.log(`Transformed wiki link query: ${transformed} from original query: ${trimmedQuery}`);
    return {
        originalQuery: trimmedQuery,
        queryString: transformed,
        wasMadeFromWikiLink: true,
        vaultName,
    };
}
/**
 *
 * Special cases:
 *
 * - Contains '.' without spaces:
 *   - 'h1.h4' -> to 'h1 h4' (this allows us to find intermediate levels of hierarchy)
 * - Ends with '.':
 *   - We have logic around for lookups that expects special behavior when lookup
 *     ends with '.' for example GoDown command expects logic such that ending
 *     the lookup with '.' expects only children to be shown.
 * */
function regularTransform(trimmedQuery, onlyDirectChildren) {
    // Regular processing:
    let queryString = NoteLookupUtils.slashToDot(trimmedQuery);
    let splitByDots;
    // When we are doing direct children lookup & when query ends with '.' we want exact
    // matches of the query. Hence we would not be splitting by dots, more info
    // on split by dots in {@link TransformedQueryString.splitByDots} documentation.
    if (!onlyDirectChildren && !queryString.endsWith(".")) {
        // https://regex101.com/r/vMwX9C/2
        const dotCandidateMatch = queryString.match(/(^[^\s]*?\.[^\s]*)/);
        if (dotCandidateMatch) {
            const dotCandidate = dotCandidateMatch[1];
            splitByDots = dotCandidate.split(".");
            queryString = queryString.replace(dotCandidate, splitByDots.join(" "));
        }
    }
    // When querying for direct children of the note then the prefix should match exactly.
    if (onlyDirectChildren &&
        !queryString.startsWith(FuseExtendedSearchConstants.PrefixExactMatch)) {
        queryString = FuseExtendedSearchConstants.PrefixExactMatch + queryString;
    }
    return {
        originalQuery: trimmedQuery,
        queryString,
        wasMadeFromWikiLink: false,
        splitByDots,
        onlyDirectChildren,
    };
}
//# sourceMappingURL=lookup.js.map