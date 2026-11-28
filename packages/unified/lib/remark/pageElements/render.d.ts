/**
 * HTML rendering helpers for Sail Note Page Elements.
 *
 * All helpers emit self-contained HTML snippets with inline styles. Inline
 * styles are used so the elements look reasonable in every rendering surface
 * (VSCode Note Preview webview, hover preview, static publishing) without
 * requiring consumers to ship extra CSS. Where possible we prefer VSCode
 * theme CSS variables with neutral fallbacks.
 */
import { NotePageElementProvider } from "./types";
/** Escape a string for safe inclusion in HTML text/attribute content. */
export declare function escapeHtml(text: string): string;
/**
 * Render the built-in help content for a page element marker. This is the
 * default content for the `PREFIX` / `POSTFIX` / `HELP` elements and lists
 * every provider currently registered.
 */
export declare function renderPageElementHelp(opts: {
    key: string;
    raw: string;
    providers: NotePageElementProvider[];
}): string;
/**
 * Render a non-fatal error box when a provider throws. Rendering errors must
 * never break the whole note render.
 */
export declare function renderPageElementError(opts: {
    key: string;
    raw: string;
    message: string;
}): string;
