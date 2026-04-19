import { DendronError } from "@saili/common-all";
// @ts-ignore - Eat type is not exported from remark-parse
type Eat = any;
import type { Plugin, Processor } from "unified";
import { DendronASTDest, DendronASTTypes, SailZenCite } from "../types";
import { MDUtilsV5 } from "..";

/**
 * Remark plugin for SailZen ::cite[keys] directive.
 *
 * Parses inline citations like:
 *   ::cite[foo, bar]
 *   ::cite[ foo , bar ]
 *
 * And produces a sailzenCite AST node.
 */

export const CITE_REGEX = /^::cite\[([^\]]*)\]/;

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
    return value.indexOf("::cite", fromIndex);
  }

  function inlineTokenizer(eat: Eat, value: string) {
    const match = CITE_REGEX.exec(value);
    if (match) {
      const rawKeys = match[1];
      const keys = rawKeys
        .split(/,\s*/)
        .map((s: string) => s.trim())
        .filter(Boolean);
      return eat(match[0])({
        type: DendronASTTypes.SAILZEN_CITE,
        keys,
      } as SailZenCite);
    }
    return;
  }
  inlineTokenizer.locator = locator;

  const Parser = proc.Parser;
  if (!Parser) return;
  const inlineTokenizers = Parser.prototype.inlineTokenizers;
  const inlineMethods = Parser.prototype.inlineMethods;
  inlineTokenizers.sailzenCite = inlineTokenizer;
  // Insert before 'text' so it takes priority over plain text
  inlineMethods.splice(inlineMethods.indexOf("text"), 0, "sailzenCite");
}

function attachCompiler(proc: Processor) {
  const Compiler = proc.Compiler;
  if (!Compiler) return;
  const visitors = Compiler.prototype.visitors;

  if (visitors) {
    visitors[DendronASTTypes.SAILZEN_CITE] = function (
      node: SailZenCite
    ): string {
      const { dest } = MDUtilsV5.getProcData(proc);
      const keys = node.keys.join(", ");
      switch (dest) {
        case DendronASTDest.MD_DENDRON:
        case DendronASTDest.MD_REGULAR:
          // In markdown modes, keep the directive as-is for round-tripping
          return `::cite[${keys}]`;
        case DendronASTDest.HTML:
          // In HTML preview, render as superscript citation numbers
          return `<sup>[${keys}]</sup>`;
        case DendronASTDest.DOC_EXPORT:
          // In doc export mode, this should be handled by backend codegen
          // Return a placeholder that backends can recognize
          return `__CITE__[${keys}]`;
        case DendronASTDest.DOC_PREVIEW:
          return `<sup class="sailzen-cite">[${keys}]</sup>`;
        default:
          throw new DendronError({
            message: `Unable to render sailzenCite for dest ${dest}`,
          });
      }
    };
  }
}

export { plugin as sailzenCite };
