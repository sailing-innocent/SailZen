/**
 * Public API types for Sail Note Page Elements.
 *
 * A "page element" is an internal, dynamically-rendered block embedded in a
 * note via a special XML-style marker, e.g.
 *
 * ```markdown
 * <sail-elem key="PREFIX" />
 * <sail-elem key="POSTFIX" />
 * <sail-elem key="WEATHER" city="hangzhou" />
 * <sail-elem key="WEATHER" city="hangzhou">fallback content</sail-elem>
 * ```
 *
 * The marker is mapped to a {@link NotePageElementProvider} through the
 * {@link PageElementRegistry}. Providers compute the actual HTML content at
 * render time, which makes it possible to inject note-aware, query-driven
 * content (e.g. a weather forecast derived from the note's date) into the
 * Note Preview without ever touching the note's source text.
 */
import {
  SailConfig,
  DVault,
  NotePropsMeta,
  ProcFlavor,
} from "@saili/common-all";

/**
 * Arguments parsed from a page element marker.
 *
 * - Marker attributes other than `key` become named arguments
 *   (`<sail-elem key="FOO" city="hangzhou" />` -> `{ _: [], city: "hangzhou" }`)
 * - `_` collects positional arguments (always empty for the XML syntax,
 *   reserved for future forms)
 */
export type PageElementArgs = { _: string[] } & Record<string, string | string[]>;

/**
 * Context handed to a provider when its element is rendered.
 */
export type PageElementRenderContext = {
  /** The note currently being rendered. */
  note: NotePropsMeta;
  /** The marker key that triggered this render (same as provider.key). */
  key: string;
  /** Parsed marker arguments. */
  args: PageElementArgs;
  /** The raw marker text as written in the note. */
  raw: string;
  /**
   * Inner content of the paired marker form, e.g.
   * `<sail-elem key="WEATHER">loading...</sail-elem>`. Providers may use it
   * as fallback content when their query fails; generic markdown renderers
   * show it as-is.
   */
  fallback?: string;
  /** Fname of the note being rendered. */
  fname: string;
  /** Vault of the note being rendered. */
  vault: DVault;
  /** All vaults in the workspace (may be empty in lightweight contexts). */
  vaults: DVault[];
  /** Workspace root, when available. */
  wsRoot?: string;
  /** Effective workspace config. */
  config: SailConfig;
  /** Render flavor (PREVIEW, PUBLISHING, HOVER_PREVIEW, ...), when known. */
  flavor?: ProcFlavor;
};

/**
 * A provider maps one marker key to dynamically generated HTML content.
 *
 * Implementations must be side-effect free with respect to the note source:
 * a provider only *reads* context and returns an HTML string.
 */
export type NotePageElementProvider = {
  /**
   * Upper-case marker key, matched by `[A-Z][A-Z0-9_]*`.
   * Example: "PREFIX", "POSTFIX", "WEATHER".
   */
  key: string;
  /** Human readable name, shown in help output. */
  title: string;
  /** Short description of what the element renders, shown in help output. */
  description: string;
  /**
   * Example usage shown in help output, e.g.
   * `<sail-elem key="WEATHER" city="hangzhou" />`.
   */
  usage?: string;
  /**
   * Optional TTL (milliseconds) for caching this provider's rendered output
   * per (note, key, args). `0` / undefined disables caching. Use this for
   * expensive or slowly-changing queries (e.g. a weather API call).
   */
  cacheTtlMs?: number;
  /**
   * Produce the HTML content for the element. May be async to allow
   * query-driven providers (HTTP, database, engine lookups, ...).
   */
  render: (ctx: PageElementRenderContext) => string | Promise<string>;
};

/**
 * Options for the remark plugin.
 */
export type PageElementsPluginOpts = {
  /**
   * Registry to resolve providers from. Defaults to the global default
   * registry (see {@link getDefaultPageElementRegistry}).
   */
  registry?: import("./registry").PageElementRegistry;
};
