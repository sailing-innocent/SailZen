import {
  ConfigUtils,
  DendronError,
  ZDOCS_HIERARCHY,
  ZDOCS_HIERARCHY_BASE,
  ZDOCS_TAG_PREFIX,
  ZDOCS_TAG_PREFIX_REGEX,
  ZDOCS_TAG_SUFFIX_REGEX
} from "@saili/common-all";
import { Element } from "hast";
// @ts-ignore - Eat type is not exported from remark-parse
type Eat = any;
import type { Plugin, Processor } from "unified";
import { SiteUtils } from "../SiteUtils";
import { DendronASTDest, DendronASTTypes, HashTag } from "../types";
import { MDUtilsV5 } from "../utilsv5";
import { PUNCTUATION_MARKS } from "./hashtag";

/** Can have period in the middle */
const GOOD_MIDDLE_CHARACTER = `[^#@|\\[\\]\\s${PUNCTUATION_MARKS}]`;
/** Can have period in the end */
const GOOD_END_CHARACTER = `[^#@|\\[\\]\\s${PUNCTUATION_MARKS}]`;

export const ZDOCTAG_REGEX = new RegExp(
  // Avoid matching it if there's a non-whitespace character before
  `^(?<!\\S)(?<tagSymbol>${ZDOCS_TAG_PREFIX_REGEX})(?<tagContents>` +
  // Match one or more valid characters inside braces
  `(?:${GOOD_MIDDLE_CHARACTER}+)?` +
  `)${ZDOCS_TAG_SUFFIX_REGEX}`
);

export const ZDOCTAG_REGEX_LOOSE = new RegExp(
  // Avoid matching it if there's a non-whitespace character before
  `(?<!\\S)(?<tagSymbol>${ZDOCS_TAG_PREFIX_REGEX})(?<zdocTagContents>` +
  // Match one or more valid characters inside braces
  `${GOOD_MIDDLE_CHARACTER}*` +
  `${GOOD_END_CHARACTER}` +
  `)${ZDOCS_TAG_SUFFIX_REGEX}`
);
export class ZDocTagUtils {
  static extractTagFromMatch(match: RegExpMatchArray | null) {
    if (match && match.groups) {
      return match.groups.tagContents || match.groups.zdocTagContents;
    }
    return;
  }

  static matchZDocTag = (
    text: string,
    matchLoose: boolean = true
  ): string | undefined => {
    const match = (matchLoose ? ZDOCTAG_REGEX : ZDOCTAG_REGEX_LOOSE).exec(text);
    return this.extractTagFromMatch(match);
  };
}

type PluginOpts = {};

const plugin: Plugin<[PluginOpts?]> = function plugin(
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
    // Do not locate a symbol if the previous character is non-whitespace.
    // Unified cals tokenizer starting at the index we return here,
    // so tokenizer won't be able to reject it for not starting with a non-space character.
    // const atSymbol = value.indexOf("@", fromIndex);
    // const atSymbol = value.indexOf("\\cite", fromIndex);
    const atSymbol = value.indexOf(ZDOCS_TAG_PREFIX, fromIndex);
    if (atSymbol === 0) {
      return atSymbol;
    } else if (atSymbol > 0) {
      const previousSymbol = value[atSymbol - 1];
      if (!previousSymbol || /[\s]/.exec(previousSymbol)) {
        return atSymbol;
      }
    }
    return -1;
  }

  function inlineTokenizer(eat: Eat, value: string) {
    const { enableZDocTags } = ConfigUtils.getWorkspace(
      MDUtilsV5.getProcData(proc).config
    );
    if (enableZDocTags === false) return;
    const match = ZDOCTAG_REGEX.exec(value);
    if (match && match.groups?.tagContents) {
      // console.log("Found user tag", match[0]);
      return eat(match[0])({
        type: DendronASTTypes.ZDOCTAG,
        // @ts-ignore
        value: match[0],
        fname: `${ZDOCS_HIERARCHY}${match.groups.tagContents}`,
      });
    }
    return;
  }
  inlineTokenizer.locator = locator;

  const Parser = proc.Parser;
  if (!Parser) return;
  const inlineTokenizers = Parser.prototype.inlineTokenizers;
  const inlineMethods = Parser.prototype.inlineMethods;
  inlineTokenizers.users = inlineTokenizer;
  inlineMethods.splice(inlineMethods.indexOf("link"), 0, ZDOCS_HIERARCHY_BASE);
}

function attachCompiler(proc: Processor, _opts?: PluginOpts) {
  const Compiler = proc.Compiler;
  if (!Compiler) return;
  const visitors = Compiler.prototype.visitors;

  if (visitors) {
    visitors.zdoctag = (node: HashTag): string | Element => {
      const { dest, config } = MDUtilsV5.getProcData(proc);
      const prefix = SiteUtils.getSitePrefixForNote(config);
      switch (dest) {
        case DendronASTDest.MD_DENDRON:
          return node.value;
        case DendronASTDest.MD_REGULAR:
        default:
          throw new DendronError({ message: "Unable to render zdoctag" });
      }
    };
  }
}

export { plugin as zdocTags };
export { PluginOpts as ZDocTagOpts };
