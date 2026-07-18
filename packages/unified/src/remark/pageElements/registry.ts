/**
 * Registry for Sail Note Page Element providers.
 *
 * The registry is the single extension point of the page element system:
 * external code (the VSCode extension, the engine server, or future agent
 * services) registers a {@link NotePageElementProvider} for a marker key,
 * and every HTML render of a note containing `$$KEY$$` will call that
 * provider to produce the element's content.
 *
 * A process-wide default registry is exposed via
 * {@link getDefaultPageElementRegistry}. It comes pre-populated with the
 * built-in `PREFIX`, `POSTFIX` and `HELP` elements, which render help text
 * until a real provider overrides them.
 */
import { SailError } from "@saili/common-all";
import { renderPageElementError, renderPageElementHelp } from "./render";
import {
  NotePageElementProvider,
  PageElementArgs,
  PageElementRenderContext,
} from "./types";

/** Marker keys must be upper-case identifiers: `[A-Z][A-Z0-9_]*`. */
export const PAGE_ELEMENT_KEY_REGEX = /^[A-Z][A-Z0-9_]{0,63}$/;

type CacheEntry = { html: string; expiresAt: number };

export class PageElementRegistry {
  private providers = new Map<string, NotePageElementProvider>();
  private cache = new Map<string, CacheEntry>();

  /**
   * Register a provider. Throws if the key is invalid or already taken,
   * unless `opts.override` is set.
   */
  register(
    provider: NotePageElementProvider,
    opts?: { override?: boolean }
  ): this {
    const key = provider.key;
    if (!PAGE_ELEMENT_KEY_REGEX.test(key)) {
      throw new SailError({
        message: `Invalid page element key "${key}". Keys must match ${PAGE_ELEMENT_KEY_REGEX}.`,
      });
    }
    if (this.providers.has(key) && !opts?.override) {
      throw new SailError({
        message: `A page element provider for "${key}" is already registered. Pass { override: true } to replace it.`,
      });
    }
    this.providers.set(key, provider);
    // Existing cached entries may belong to the previous provider.
    this.invalidateKey(key);
    return this;
  }

  /** Remove a provider. Returns true if one was registered. */
  unregister(key: string): boolean {
    this.invalidateKey(key);
    return this.providers.delete(key);
  }

  has(key: string): boolean {
    return this.providers.has(key);
  }

  get(key: string): NotePageElementProvider | undefined {
    return this.providers.get(key);
  }

  /** All registered providers, sorted by key for stable help output. */
  list(): NotePageElementProvider[] {
    return [...this.providers.values()].sort((a, b) =>
      a.key.localeCompare(b.key)
    );
  }

  /**
   * Render the content HTML for `key`. Never throws: provider failures are
   * converted into a non-fatal error box so a single broken element cannot
   * break the whole note render.
   */
  async render(
    key: string,
    ctx: Omit<PageElementRenderContext, "key">
  ): Promise<string> {
    const provider = this.providers.get(key);
    if (!provider) {
      // Unregistered keys are left untouched by the plugin, so reaching this
      // branch means the provider disappeared mid-render. Degrade to help.
      return renderPageElementHelp({
        key,
        raw: ctx.raw,
        providers: this.list(),
      });
    }

    const fullCtx: PageElementRenderContext = { ...ctx, key };
    const cacheKey = this.makeCacheKey(key, fullCtx);
    const cached = cacheKey ? this.cache.get(cacheKey) : undefined;
    if (cached && cached.expiresAt > Date.now()) {
      return cached.html;
    }

    let html: string;
    try {
      html = await provider.render(fullCtx);
    } catch (err: any) {
      html = renderPageElementError({
        key,
        raw: ctx.raw,
        message: err?.message ?? String(err),
      });
      // Do not cache failures: the next render should retry.
      return html;
    }

    if (cacheKey) {
      this.cache.set(cacheKey, {
        html,
        expiresAt: Date.now() + provider.cacheTtlMs!,
      });
    }
    return html;
  }

  /** Drop all cached provider output. */
  clearCache(): void {
    this.cache.clear();
  }

  private invalidateKey(key: string): void {
    for (const cacheKey of this.cache.keys()) {
      if (cacheKey.startsWith(`${key}:`)) {
        this.cache.delete(cacheKey);
      }
    }
  }

  private makeCacheKey(
    key: string,
    ctx: PageElementRenderContext
  ): string | undefined {
    const provider = this.providers.get(key);
    if (!provider?.cacheTtlMs || provider.cacheTtlMs <= 0) {
      return undefined;
    }
    return [
      key,
      ctx.note.id,
      ctx.note.contentHash ?? "",
      stableSerializeArgs(ctx.args),
    ].join(":");
  }
}

function stableSerializeArgs(args: PageElementArgs): string {
  const { _, ...named } = args;
  const namedPart = Object.keys(named)
    .sort()
    .map((k) => `${k}=${named[k]}`)
    .join(",");
  return [..._, namedPart].join(",");
}

// ---------------------------------------------------------------------------
// Built-in providers
// ---------------------------------------------------------------------------

/**
 * Create a built-in, help-backed provider. Until overridden, `PREFIX`,
 * `POSTFIX` and `HELP` all render usage help so that the feature is
 * discoverable out of the box.
 */
function createHelpProvider(opts: {
  key: string;
  title: string;
  description: string;
}): NotePageElementProvider {
  return {
    key: opts.key,
    title: opts.title,
    description: opts.description,
    usage: `<sail-elem key="${opts.key}" />`,
    render: (ctx) =>
      renderPageElementHelp({
        key: opts.key,
        raw: ctx.raw,
        providers: getDefaultPageElementRegistry().list(),
      }),
  };
}

/** Key of the element conventionally placed right below the frontmatter. */
export const PAGE_ELEMENT_PREFIX_KEY = "PREFIX";
/** Key of the element conventionally placed at the very end of the note. */
export const PAGE_ELEMENT_POSTFIX_KEY = "POSTFIX";
/** Key of the element that always renders the help overview. */
export const PAGE_ELEMENT_HELP_KEY = "HELP";

function createDefaultRegistry(): PageElementRegistry {
  const registry = new PageElementRegistry();
  registry.register(
    createHelpProvider({
      key: PAGE_ELEMENT_PREFIX_KEY,
      title: "Note Prefix",
      description:
        "Top area of the note (below metadata, above content). Override this provider to inject note-aware header content.",
    })
  );
  registry.register(
    createHelpProvider({
      key: PAGE_ELEMENT_POSTFIX_KEY,
      title: "Note Postfix",
      description:
        "Bottom area of the note (below all content). Override this provider to inject note-aware footer content.",
    })
  );
  registry.register(
    createHelpProvider({
      key: PAGE_ELEMENT_HELP_KEY,
      title: "Page Element Help",
      description:
        "Shows this help overview listing all registered page elements and their usage.",
    })
  );
  return registry;
}

let defaultRegistry: PageElementRegistry | undefined;

/**
 * Process-wide default registry used by the remark plugin when no explicit
 * registry is configured. Register future providers (weather, project info,
 * ...) here at extension/engine startup.
 */
export function getDefaultPageElementRegistry(): PageElementRegistry {
  if (!defaultRegistry) {
    defaultRegistry = createDefaultRegistry();
  }
  return defaultRegistry;
}

/** Test hook: reset the default registry to its built-in state. */
export function resetDefaultPageElementRegistry(): void {
  defaultRegistry = undefined;
}
