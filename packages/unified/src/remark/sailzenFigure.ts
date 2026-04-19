import { DendronError } from "@saili/common-all";
// @ts-ignore - Eat type is not exported from remark-parse
type Eat = any;
import type { Plugin, Processor } from "unified";
import { DendronASTDest, DendronASTTypes, SailZenFigure } from "../types";
import { MDUtilsV5 } from "..";

/**
 * Remark plugin for SailZen ::figure[caption](src){opts} directive.
 *
 * Parses figure directives like:
 *   ::figure[Overview of our method](fig_teaser){width="\linewidth"}
 *   ::figure[Comparison table](tab_results){columns="l c c"}
 *
 * And produces a sailzenFigure AST node.
 */

// Match ::figure[caption](src){opts} where opts is optional
export const FIGURE_REGEX =
  /^::figure\[([^\]]*)\]\s*\(([^)]+)\)(?:\s*\{([^}]*)\})?/;

type PluginOpts = {};

const plugin: Plugin<[PluginOpts?]> = function (
  this: Processor,
  _opts?: PluginOpts
) {
  attachParser(this);
  if (this.Compiler != null) {
    attachCompiler(this);
  }
};

function attachParser(proc: Processor) {
  function locator(value: string, fromIndex: number) {
    return value.indexOf("::figure", fromIndex);
  }

  function inlineTokenizer(eat: Eat, value: string) {
    const match = FIGURE_REGEX.exec(value);
    if (match) {
      const caption = match[1].trim();
      const src = match[2].trim();
      const optsRaw = match[3] || "";
      const options = parseOptions(optsRaw);
      return eat(match[0])({
        type: DendronASTTypes.SAILZEN_FIGURE,
        caption,
        src,
        options,
      } as SailZenFigure);
    }
    return;
  }
  inlineTokenizer.locator = locator;

  const Parser = proc.Parser;
  if (!Parser) return;
  const inlineTokenizers = Parser.prototype.inlineTokenizers;
  const inlineMethods = Parser.prototype.inlineMethods;
  inlineTokenizers.sailzenFigure = inlineTokenizer;
  inlineMethods.splice(inlineMethods.indexOf("text"), 0, "sailzenFigure");
}

/**
 * Parse option string like: width="\linewidth", label="fig:teaser"
 * into a Record.
 */
function parseOptions(raw: string): Record<string, any> {
  const options: Record<string, any> = {};
  if (!raw.trim()) return options;

  // Simple key="value" or key=value parser
  const regex = /(\w+)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s,]+))/g;
  let m;
  while ((m = regex.exec(raw)) !== null) {
    const key = m[1];
    const value = m[2] !== undefined ? m[2] : m[3] !== undefined ? m[3] : m[4];
    options[key] = value;
  }
  return options;
}

function attachCompiler(proc: Processor) {
  const Compiler = proc.Compiler;
  if (!Compiler) return;
  const visitors = Compiler.prototype.visitors;

  if (visitors) {
    visitors[DendronASTTypes.SAILZEN_FIGURE] = function (
      node: SailZenFigure
    ): string {
      const { dest } = MDUtilsV5.getProcData(proc);
      const { caption, src, options } = node;
      switch (dest) {
        case DendronASTDest.MD_DENDRON:
        case DendronASTDest.MD_REGULAR:
          return `::figure[${caption}](${src})${
            options && Object.keys(options).length
              ? "{" + JSON.stringify(options) + "}"
              : ""
          }`;
        case DendronASTDest.HTML:
          return `<figure>\n  <img src="${src}" alt="${caption}" />\n  <figcaption>${caption}</figcaption>\n</figure>`;
        case DendronASTDest.DOC_EXPORT:
          return `__FIGURE__[${src}|${caption}]`;
        case DendronASTDest.DOC_PREVIEW:
          return `<figure class="sailzen-figure">\n  <div class="sailzen-figure-placeholder">📷 ${src}</div>\n  <figcaption>${caption}</figcaption>\n</figure>`;
        default:
          throw new DendronError({
            message: `Unable to render sailzenFigure for dest ${dest}`,
          });
      }
    };
  }
}

export { plugin as sailzenFigure };
