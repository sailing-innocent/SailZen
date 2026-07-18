/**
 * Remark plugin for Sail Note Page Elements.
 *
 * Transforms a standalone page element marker — an XML-style custom element —
 *
 * ```markdown
 * <sail-elem key="PREFIX" />
 * <sail-elem key="WEATHER" city="hangzhou" />
 * <sail-elem key="WEATHER" city="hangzhou">fallback content</sail-elem>
 * ```
 *
 * into a {@link PageElement} AST node. When rendering to HTML, the node's
 * content is resolved through the {@link PageElementRegistry} and injected as
 * a `<div class="sail-page-element ...">` wrapper via `data.hName` /
 * `data.hChildren` (supported by mdast-util-to-hast), so the Note Preview
 * shows live provider content while the note source keeps only the marker.
 *
 * Why XML syntax?
 *
 * - No conflict with LaTeX math (`$$...$$`), wikilinks, or any other Sail
 *   syntax — markdown parsers treat the marker as a raw `html` node.
 * - Graceful degradation: generic markdown renderers (GitHub, editors
 *   without this plugin) fall back to rendering the unknown tag as a plain
 *   (empty) element, or show the inner fallback content for the paired form.
 *
 * Design notes:
 *
 * - Only markers whose key is *registered* in the registry are transformed.
 *   Unregistered keys pass through as raw HTML, which is exactly the generic
 *   fallback behavior.
 * - The plugin is round-trip safe: stringifying back to markdown yields the
 *   original marker text (see the toMarkdown extension below).
 * - Provider rendering only happens for HTML destinations in FULL mode; all
 *   other uses (decorations scan, refactor parse/stringify, ...) pay nothing
 *   but a cheap tag-name test per html node.
 */
import { SailASTDest } from "@saili/common-all";
import type { Node, Parent } from "mdast";
import type { Plugin, Processor } from "unified";
import type {
  Options as ToMarkdownExtension,
  Handle as ToMarkdownHandle,
} from "mdast-util-to-markdown";
import { visit } from "unist-util-visit";
import { SailASTTypes } from "../../types";
import { MDUtilsV5, ProcMode } from "../../utilsv5";
import {
  getDefaultPageElementRegistry,
  PAGE_ELEMENT_KEY_REGEX,
  PageElementRegistry,
} from "./registry";
import { PageElementArgs, PageElementsPluginOpts } from "./types";

/** Tag name of page element markers. */
export const SAIL_ELEM_TAG = "sail-elem";

/** Attribute carrying the element key. */
export const SAIL_ELEM_KEY_ATTR = "key";

/**
 * Self-closing form: `<sail-elem key="PREFIX" />`. The whole html node must be
 * exactly the tag. Attribute values must not contain `>`.
 */
const SELF_CLOSING_REGEX = /^<sail-elem\b([\s\S]*?)\/>$/;

/**
 * Paired form: `<sail-elem key="PREFIX">fallback</sail-elem>`. May span
 * multiple lines (markdown keeps a raw html block together until a blank
 * line). The inner content is preserved as fallback.
 */
const PAIRED_REGEX = /^<sail-elem\b([\s\S]*?)>([\s\S]*)<\/sail-elem\s*>$/;

/**
 * Attribute tokenizer: `name`, `name=value`, `name="value"`, `name='value'`.
 */
const ATTR_REGEX =
  /([^\s"'=\/<>]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+)))?/g;

export type ParsedSailElem = {
  /** Element key, e.g. "PREFIX". Undefined when the key attr is missing. */
  key?: string;
  /** Named arguments from attributes other than `key`. */
  args: PageElementArgs;
  /** Inner fallback content of the paired form. */
  fallback?: string;
  /** The full original marker text, used for lossless round-trips. */
  raw: string;
};

/**
 * Parse a raw html node value into a page element marker. Returns undefined
 * when the value is not exactly one marker element.
 */
export function parseSailElem(rawValue: string): ParsedSailElem | undefined {
  const raw = rawValue.trim();

  let attrsRaw: string | undefined;
  let fallback: string | undefined;

  const selfClosing = SELF_CLOSING_REGEX.exec(raw);
  if (selfClosing) {
    attrsRaw = selfClosing[1];
  } else {
    const paired = PAIRED_REGEX.exec(raw);
    if (!paired) {
      return undefined;
    }
    attrsRaw = paired[1];
    fallback = paired[2];
  }

  const args: PageElementArgs = { _: [] };
  let key: string | undefined;
  for (const m of attrsRaw.matchAll(ATTR_REGEX)) {
    const name = m[1];
    const value = m[2] ?? m[3] ?? m[4] ?? "true";
    if (name === SAIL_ELEM_KEY_ATTR) {
      key = value;
    } else {
      args[name] = value;
    }
  }

  if (key === undefined) {
    return undefined;
  }
  return { key, args, fallback, raw };
}

/**
 * mdast-util-to-markdown extension so the node stringifies back to its
 * original marker text. This keeps parse -> stringify round-trips lossless
 * (e.g. PreviewPanel's image URL rewrite, refactor commands, ...).
 */
function createToMarkdownExtension(): ToMarkdownExtension {
  const handlePageElement: ToMarkdownHandle = function (node) {
    const el = node as unknown as { raw?: string };
    return el.raw ?? "";
  };
  return {
    handlers: {
      [SailASTTypes.PAGE_ELEMENT]: handlePageElement,
    } as any,
  };
}

const plugin: Plugin<[PageElementsPluginOpts?], any> = function (
  this: Processor,
  opts?: PageElementsPluginOpts
) {
  const proc = this;
  const registry: PageElementRegistry =
    opts?.registry ?? getDefaultPageElementRegistry();

  // Round-trip serialization support.
  const data = proc.data();
  const toMarkdownExtensions =
    (data.toMarkdownExtensions as ToMarkdownExtension[]) || [];
  toMarkdownExtensions.push(createToMarkdownExtension());
  data.toMarkdownExtensions = toMarkdownExtensions;

  return async (tree: Node) => {
    // ------------------------------------------------------------------
    // Pass 1 (cheap, all modes/dests): marker html node -> PageElement node.
    // ------------------------------------------------------------------
    const elements: Array<{
      node: any;
      key: string;
      args: PageElementArgs;
      fallback?: string;
      raw: string;
    }> = [];

    visit(
      tree as any,
      "html",
      (htmlNode: Node & { value?: string }, index, parent: Parent) => {
        if (index === undefined || !parent || typeof htmlNode.value !== "string") {
          return;
        }
        // Only standalone block-level markers are transformed. Inline tags
        // inside phrasing content (paragraphs, headings) are left as raw
        // html — markers are block-level page areas by design.
        if (parent.type === "paragraph" || parent.type === "heading") {
          return;
        }
        const parsed = parseSailElem(htmlNode.value);
        if (!parsed || parsed.key === undefined) {
          return;
        }
        if (
          !PAGE_ELEMENT_KEY_REGEX.test(parsed.key) ||
          !registry.has(parsed.key)
        ) {
          // Conservative: only registered keys become elements. Unregistered
          // markers stay raw HTML, which is the generic fallback behavior.
          return;
        }
        const node = {
          type: SailASTTypes.PAGE_ELEMENT,
          key: parsed.key,
          args: parsed.args,
          raw: parsed.raw,
          position: htmlNode.position,
          data: {},
        };
        (parent.children as any[])[index] = node;
        elements.push({
          node,
          key: parsed.key,
          args: parsed.args,
          fallback: parsed.fallback,
          raw: parsed.raw,
        });
      }
    );

    if (elements.length === 0) {
      return;
    }

    // ------------------------------------------------------------------
    // Pass 2 (HTML rendering only): resolve content through the registry.
    // ------------------------------------------------------------------
    const procOpts = MDUtilsV5.getProcOpts(proc);
    if (procOpts.mode !== ProcMode.FULL) {
      return;
    }
    const procData = MDUtilsV5.getProcData(proc);
    if (procData.dest !== SailASTDest.HTML) {
      return;
    }

    const baseCtx = {
      note: procData.noteToRender,
      fname: procData.fname,
      vault: procData.vault,
      vaults: procData.vaults ?? [],
      wsRoot: procData.wsRoot,
      config: procData.config,
      flavor: procOpts.flavor,
    };

    await Promise.all(
      elements.map(async ({ node, key, args, fallback, raw }) => {
        const html = await registry.render(key, {
          ...baseCtx,
          args,
          fallback,
          raw,
        });
        node.data = {
          ...node.data,
          hName: "div",
          hProperties: {
            className: [
              "sail-page-element",
              `sail-page-element-${key.toLowerCase()}`,
            ],
            dataPageElement: key,
          },
          hChildren: [{ type: "raw", value: html }],
        };
      })
    );
  };
};

export { plugin as pageElements };
