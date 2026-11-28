import { genDefaultGithubConfig, githubSchema } from "./github";
import { genDefaultSEOConfig, seoSchema } from "./seo";
import { z, schemaForType } from "../../../parse";
export var Theme;
(function (Theme) {
    Theme["DARK"] = "dark";
    Theme["LIGHT"] = "light";
    Theme["CUSTOM"] = "custom";
})(Theme || (Theme = {}));
export var SearchMode;
(function (SearchMode) {
    SearchMode["SEARCH"] = "search";
    SearchMode["LOOKUP"] = "lookup";
})(SearchMode || (SearchMode = {}));
const searchModeSchema = z.enum([SearchMode.SEARCH, SearchMode.LOOKUP]);
export const publishingSchema = schemaForType()(z
    .object({
    enableFMTitle: z.boolean().optional().default(true),
    // enableHierarchyDisplay?: boolean;
    // hierarchyDisplayTitle?: string;
    enableNoteTitleForLink: z.boolean().optional().default(true),
    enablePrettyRefs: z.boolean().optional().default(true),
    // enableBackLinks?: boolean;
    enableKatex: z.boolean().optional().default(true),
    //
    // assetsPrefix?: string;
    copyAssets: z.boolean().default(true),
    //
    // canonicalBaseUrl?: string;
    // customHeaderPath?: string;
    // ga?: GoogleAnalyticsConfig;
    // logoPath?: string;
    // siteFaviconPath?: string;
    // siteIndex?: string;
    siteHierarchies: z.array(z.string()).default(["root"]),
    writeStubs: z.boolean().default(false),
    siteRootDir: z.string().default("docs"),
    seo: seoSchema,
    github: githubSchema.optional(),
    enableSiteLastModified: z.boolean().default(true),
    // siteUrl?: string;
    enableFrontmatterTags: z.boolean().default(true),
    enableHashesForFMTags: z.boolean().default(false),
    enableRandomlyColoredTags: z.boolean().optional().default(true),
    enableTaskNotes: z.boolean().optional().default(true),
    // hierarchy?: { [key: string]: HierarchyConfig };
    // duplicateNoteBehavior?: DuplicateNoteBehavior;
    // theme?: Theme;
    // segmentKey?: string;
    // cognitoUserPoolId?: string;
    // cognitoClientId?: string;
    enablePrettyLinks: z.boolean().default(true),
    // siteBanner?: string;
    // giscus?: GiscusConfig;
    // sidebarPath?: string | false;
    searchMode: searchModeSchema.optional().default(SearchMode.LOOKUP),
})
    .passthrough());
/**
 * Generate default {@link SailPublishingConfig}
 * @returns SailPublishingConfig
 */
export function genDefaultPublishingConfig() {
    return {
        enableFMTitle: true,
        enableNoteTitleForLink: true,
        enablePrettyRefs: true,
        enableKatex: true,
        copyAssets: true,
        siteHierarchies: ["root"],
        writeStubs: false,
        siteRootDir: "docs",
        seo: genDefaultSEOConfig(),
        github: genDefaultGithubConfig(),
        enableSiteLastModified: true,
        enableFrontmatterTags: true,
        enableHashesForFMTags: false,
        enableRandomlyColoredTags: true,
        enableTaskNotes: true,
        enablePrettyLinks: true,
        searchMode: SearchMode.LOOKUP,
    };
}
//# sourceMappingURL=publishing.js.map