import { DVault } from "../../DVault";
import { GiscusConfig } from "./giscus";
import { GithubConfig } from "./github";
import { SEOConfig } from "./seo";
import { z } from "../../../parse";
export declare enum Theme {
    DARK = "dark",
    LIGHT = "light",
    CUSTOM = "custom"
}
export declare enum SearchMode {
    SEARCH = "search",
    LOOKUP = "lookup"
}
/**
 * Namespace for all publishing related configurations
 */
export type SailPublishingConfig = {
    enableFMTitle?: boolean;
    enableHierarchyDisplay?: boolean;
    hierarchyDisplayTitle?: string;
    enableNoteTitleForLink?: boolean;
    enablePrettyRefs?: boolean;
    enableBackLinks?: boolean;
    enableKatex?: boolean;
    assetsPrefix?: string;
    copyAssets: boolean;
    canonicalBaseUrl?: string;
    customHeaderPath?: string;
    ga?: GoogleAnalyticsConfig;
    logoPath?: string;
    siteFaviconPath?: string;
    siteIndex?: string;
    siteHierarchies: string[];
    enableSiteLastModified: boolean;
    siteRootDir: string;
    siteUrl?: string;
    enableFrontmatterTags: boolean;
    enableHashesForFMTags: boolean;
    enableRandomlyColoredTags?: boolean;
    enableTaskNotes?: boolean;
    hierarchy?: {
        [key: string]: HierarchyConfig;
    };
    duplicateNoteBehavior?: DuplicateNoteBehavior;
    writeStubs: boolean;
    seo: SEOConfig;
    github?: GithubConfig;
    theme?: Theme;
    segmentKey?: string;
    cognitoUserPoolId?: string;
    cognitoClientId?: string;
    enablePrettyLinks: boolean;
    siteBanner?: string;
    giscus?: GiscusConfig;
    sidebarPath?: string | false;
    searchMode?: SearchMode;
};
export type CleanSailPublishingConfig = SailPublishingConfig & Required<Pick<SailPublishingConfig, "siteIndex" | "siteUrl">>;
export type DuplicateNoteAction = "useVault";
export type UseVaultBehaviorPayload = {
    vault: DVault;
} | string[];
export type DuplicateNoteActionPayload = UseVaultBehaviorPayload;
export type UseVaultBehavior = {
    action: DuplicateNoteAction;
    payload: DuplicateNoteActionPayload;
};
export type DuplicateNoteBehavior = UseVaultBehavior;
export type HierarchyConfig = {
    publishByDefault?: boolean | {
        [key: string]: boolean;
    };
    customFrontmatter?: CustomFMEntry[];
};
export type CustomFMEntry = {
    key: string;
    value: any;
};
export type GoogleAnalyticsConfig = {
    tracking?: string;
};
export declare const publishingSchema: z.ZodObject<{
    enableFMTitle: z.ZodDefault<z.ZodOptional<z.ZodBoolean>>;
    enableNoteTitleForLink: z.ZodDefault<z.ZodOptional<z.ZodBoolean>>;
    enablePrettyRefs: z.ZodDefault<z.ZodOptional<z.ZodBoolean>>;
    enableKatex: z.ZodDefault<z.ZodOptional<z.ZodBoolean>>;
    copyAssets: z.ZodDefault<z.ZodBoolean>;
    siteHierarchies: z.ZodDefault<z.ZodArray<z.ZodString>>;
    writeStubs: z.ZodDefault<z.ZodBoolean>;
    siteRootDir: z.ZodDefault<z.ZodString>;
    seo: z.ZodObject<{
        title: z.ZodDefault<z.ZodOptional<z.ZodString>>;
        description: z.ZodDefault<z.ZodOptional<z.ZodString>>;
        author: z.ZodOptional<z.ZodString>;
        twitter: z.ZodOptional<z.ZodString>;
        image: z.ZodOptional<z.ZodObject<{
            url: z.ZodString;
            alt: z.ZodString;
        }, z.core.$strip>>;
    }, z.core.$strip>;
    github: z.ZodOptional<z.ZodObject<{
        cname: z.ZodOptional<z.ZodString>;
        enableEditLink: z.ZodDefault<z.ZodBoolean>;
        editLinkText: z.ZodDefault<z.ZodOptional<z.ZodString>>;
        editBranch: z.ZodDefault<z.ZodOptional<z.ZodString>>;
        editViewMode: z.ZodDefault<z.ZodOptional<z.ZodUnion<readonly [z.ZodLiteral<import("./github").GithubEditViewModeEnum.tree>, z.ZodLiteral<import("./github").GithubEditViewModeEnum.edit>]>>>;
        editRepository: z.ZodOptional<z.ZodString>;
    }, z.core.$strip>>;
    enableSiteLastModified: z.ZodDefault<z.ZodBoolean>;
    enableFrontmatterTags: z.ZodDefault<z.ZodBoolean>;
    enableHashesForFMTags: z.ZodDefault<z.ZodBoolean>;
    enableRandomlyColoredTags: z.ZodDefault<z.ZodOptional<z.ZodBoolean>>;
    enableTaskNotes: z.ZodDefault<z.ZodOptional<z.ZodBoolean>>;
    enablePrettyLinks: z.ZodDefault<z.ZodBoolean>;
    searchMode: z.ZodDefault<z.ZodOptional<z.ZodEnum<{
        search: SearchMode.SEARCH;
        lookup: SearchMode.LOOKUP;
    }>>>;
}, z.core.$loose>;
/**
 * Generate default {@link SailPublishingConfig}
 * @returns SailPublishingConfig
 */
export declare function genDefaultPublishingConfig(): SailPublishingConfig;
