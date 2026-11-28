import { NotePageElementProvider, PageElementRenderContext } from "./types";
/** Marker keys must be upper-case identifiers: `[A-Z][A-Z0-9_]*`. */
export declare const PAGE_ELEMENT_KEY_REGEX: RegExp;
export declare class PageElementRegistry {
    private providers;
    private cache;
    /**
     * Register a provider. Throws if the key is invalid or already taken,
     * unless `opts.override` is set.
     */
    register(provider: NotePageElementProvider, opts?: {
        override?: boolean;
    }): this;
    /** Remove a provider. Returns true if one was registered. */
    unregister(key: string): boolean;
    has(key: string): boolean;
    get(key: string): NotePageElementProvider | undefined;
    /** All registered providers, sorted by key for stable help output. */
    list(): NotePageElementProvider[];
    /**
     * Render the content HTML for `key`. Never throws: provider failures are
     * converted into a non-fatal error box so a single broken element cannot
     * break the whole note render.
     */
    render(key: string, ctx: Omit<PageElementRenderContext, "key">): Promise<string>;
    /** Drop all cached provider output. */
    clearCache(): void;
    private invalidateKey;
    private makeCacheKey;
}
/** Key of the element conventionally placed right below the frontmatter. */
export declare const PAGE_ELEMENT_PREFIX_KEY = "PREFIX";
/** Key of the element conventionally placed at the very end of the note. */
export declare const PAGE_ELEMENT_POSTFIX_KEY = "POSTFIX";
/** Key of the element that always renders the help overview. */
export declare const PAGE_ELEMENT_HELP_KEY = "HELP";
/**
 * Process-wide default registry used by the remark plugin when no explicit
 * registry is configured. Register future providers (weather, project info,
 * ...) here at extension/engine startup.
 */
export declare function getDefaultPageElementRegistry(): PageElementRegistry;
/** Test hook: reset the default registry to its built-in state. */
export declare function resetDefaultPageElementRegistry(): void;
