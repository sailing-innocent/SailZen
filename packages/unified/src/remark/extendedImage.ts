import _ from "lodash";
import { DendronError } from "@saili/common-all";
// @ts-ignore - Eat type is not exported from remark-parse
type Eat = any;
import type { Plugin, Processor } from "unified";
import { DendronASTDest, DendronASTTypes, ExtendedImage } from "../types";
import { Element } from "hast";
import { html } from "mdast-builder";
import YAML from "js-yaml";
import { MDUtilsV5 } from "../utilsv5";

export const EXTENDED_IMAGE_REGEX =
  /^!\[(?<alt>[^[\]]*)\]\((?<url>.*)\)(?<props>{[^{}]*})/;
export const EXTENDED_IMAGE_REGEX_LOOSE =
  /!\[(?<alt>[^[\]]*)\]\((?<url>.*)\)(?<props>{[^{}]*})/;

export const matchExtendedImage = (
  text: string,
  matchLoose: boolean = true
): string | undefined => {
  const match = (
    matchLoose ? EXTENDED_IMAGE_REGEX_LOOSE : EXTENDED_IMAGE_REGEX
  ).exec(text);
  if (match && match.groups?.url && match.groups) return match[1];
  return undefined;
};

type PluginOpts = {};

const plugin: Plugin<[PluginOpts?]> = function (
  this: Processor,
  opts?: PluginOpts
) {
  attachParser(this);
  if (this.Compiler != null) {
    attachCompiler(this, opts);
  }
};

function attachParser(proc: Processor) {
  function locator(value: string, fromIndex: number) {
    return value.indexOf("!", fromIndex);
  }

  function inlineTokenizer(eat: Eat, value: string) {
    const match = EXTENDED_IMAGE_REGEX.exec(value);
    if (match && match.groups?.url) {
      let props: { [key: string]: any } = {};
      try {
        props = YAML.load(match.groups.props) as any;
      } catch {
        // Reject bad props so that it falls back to a regular image
        return;
      }

      return eat(match[0])({
        type: DendronASTTypes.EXTENDED_IMAGE,
        // @ts-ignore
        value,
        url: match.groups.url,
        alt: match.groups.alt,
        props,
      });
    }
    return;
  }
  inlineTokenizer.locator = locator;

  const Parser = proc.Parser;
  if (!Parser) return;
  const inlineTokenizers = Parser.prototype.inlineTokenizers;
  const inlineMethods = Parser.prototype.inlineMethods;
  inlineTokenizers.extendedImage = inlineTokenizer;
  inlineMethods.splice(inlineMethods.indexOf("link"), 0, "extendedImage");
}

function attachCompiler(proc: Processor, _opts?: PluginOpts) {
  const Compiler = proc.Compiler;
  if (!Compiler) return;
  const visitors = Compiler.prototype.visitors;

  if (visitors) {
    visitors.extendedImage = function (node: ExtendedImage): string | Element {
      const { dest } = MDUtilsV5.getProcData(proc);
      const alt = node.alt ? node.alt : "";
      switch (dest) {
        case DendronASTDest.MD_DENDRON:
          return `![${alt}](${node.url})${_.trim(
            YAML.dump(node.props, {
              /* Inline-only so we get JSON style {foo: bar} */
              flowLevel: 0,
            })
          )}`;
        case DendronASTDest.MD_REGULAR:
          return `![${alt}](${node.url})`;
        case DendronASTDest.MD_ENHANCED_PREVIEW:
          return extendedImage2htmlRaw(node);
        default:
          throw new DendronError({
            message: "Unable to render extended image",
          });
      }
    };
  }
}

const ALLOWED_STYLE_PROPS = new Set<string>([
  "width",
  "height",
  "float",
  "border",
  "margin",
  "padding",
  "min-width",
  "min-height",
  "max-width",
  "max-height",
  "display",
  "opacity",
  "outline",
  "rotate",
  "transition",
  "transform-origin",
  "transform",
  "z-index",
]);

export function extendedImage2htmlRaw(node: ExtendedImage, _opts?: PluginOpts) {
  const stylesList: string[] = [];
  const nodePropsList: string[] = [];
  for (const [prop, value] of Object.entries(node.props)) {
    if (ALLOWED_STYLE_PROPS.has(prop)) stylesList.push(`${prop}:${value};`);
  }
  nodePropsList.push(`src="${node.url}"`);
  if (node.alt) nodePropsList.push(`alt="${node.alt}"`);

  return `<img ${nodePropsList.join(" ")} style="${stylesList.join("")}">`;
}

export function extendedImage2html(node: ExtendedImage, opts?: PluginOpts): ReturnType<typeof html> {
  return html(extendedImage2htmlRaw(node, opts));
}

export { plugin as extendedImage };
export { PluginOpts as ExtendedImageOpts };
