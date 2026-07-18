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
export function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

const CONTAINER_STYLE = [
  "border: 1px dashed var(--vscode-panel-border, #d0d7de)",
  "border-radius: 6px",
  "padding: 8px 12px",
  "margin: 8px 0",
  "font-size: 0.9em",
  "color: var(--vscode-descriptionForeground, #6a737d)",
  "background: var(--vscode-textBlockQuote-background, rgba(127,127,127,0.05))",
].join("; ");

const TITLE_STYLE = [
  "font-weight: 600",
  "margin-bottom: 4px",
  "color: var(--vscode-foreground, #24292f)",
].join("; ");

const CODE_STYLE = [
  "font-family: var(--vscode-editor-font-family, monospace)",
  "background: var(--vscode-textCodeBlock-background, rgba(127,127,127,0.15))",
  "border-radius: 3px",
  "padding: 0 4px",
].join("; ");

const TABLE_STYLE = ["border-collapse: collapse", "width: 100%"].join("; ");

const CELL_STYLE = [
  "border: 1px solid var(--vscode-panel-border, #d0d7de)",
  "padding: 4px 8px",
  "text-align: left",
  "vertical-align: top",
].join("; ");

/**
 * Render the built-in help content for a page element marker. This is the
 * default content for the `PREFIX` / `POSTFIX` / `HELP` elements and lists
 * every provider currently registered.
 */
export function renderPageElementHelp(opts: {
  key: string;
  raw: string;
  providers: NotePageElementProvider[];
}): string {
  const { key, raw, providers } = opts;
  const rows = providers
    .map((p) => {
      const usage = escapeHtml(p.usage ?? `$$${p.key}$$`);
      return [
        `<tr>`,
        `<td style="${CELL_STYLE}"><code style="${CODE_STYLE}">${usage}</code></td>`,
        `<td style="${CELL_STYLE}">${escapeHtml(p.title)}</td>`,
        `<td style="${CELL_STYLE}">${escapeHtml(p.description)}</td>`,
        `</tr>`,
      ].join("");
    })
    .join("");

  return [
    `<div class="sail-page-element-help" style="${CONTAINER_STYLE}">`,
    `<div style="${TITLE_STYLE}">Sail Page Element: <code style="${CODE_STYLE}">${escapeHtml(raw)}</code></div>`,
    `<div style="margin-bottom: 8px;">`,
    `This placeholder renders dynamic content for the `,
    `<code style="${CODE_STYLE}">${escapeHtml(key)}</code> page element. `,
    `Place <code style="${CODE_STYLE}">${escapeHtml('<sail-elem key="PREFIX" />')}</code> directly below the frontmatter to inject a top area, `,
    `and <code style="${CODE_STYLE}">${escapeHtml('<sail-elem key="POSTFIX" />')}</code> at the end of the note for a bottom area. `,
    `Register a custom provider to replace this help text with live content.`,
    `</div>`,
    `<table style="${TABLE_STYLE}">`,
    `<thead><tr>`,
    `<th style="${CELL_STYLE}">Marker</th>`,
    `<th style="${CELL_STYLE}">Name</th>`,
    `<th style="${CELL_STYLE}">Description</th>`,
    `</tr></thead>`,
    `<tbody>${rows}</tbody>`,
    `</table>`,
    `</div>`,
  ].join("");
}

/**
 * Render a non-fatal error box when a provider throws. Rendering errors must
 * never break the whole note render.
 */
export function renderPageElementError(opts: {
  key: string;
  raw: string;
  message: string;
}): string {
  const { key, raw, message } = opts;
  return [
    `<div class="sail-page-element-error" style="${CONTAINER_STYLE}; border-color: var(--vscode-editorError-foreground, #cf222e)">`,
    `<div style="${TITLE_STYLE}; color: var(--vscode-editorError-foreground, #cf222e)">`,
    `Page element <code style="${CODE_STYLE}">${escapeHtml(raw)}</code> (${escapeHtml(key)}) failed to render`,
    `</div>`,
    `<div>${escapeHtml(message)}</div>`,
    `</div>`,
  ].join("");
}
