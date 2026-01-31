/* eslint-disable func-names */
import {
  ConfigUtils,
  CONSTANTS,
  DendronError,
  NoteDictsUtils,
  NoteUtils,
  Position,
  VaultUtils,
} from "@saili/common-all";
import _ from "lodash";
import type { Plugin, Processor } from "unified";
import type { Extension as MicromarkExtension, Tokenizer, State, Effects, Code } from "micromark-util-types";
import type { Extension as FromMarkdownExtension, Handle } from "mdast-util-from-markdown";
import type { Options as ToMarkdownExtension, Handle as ToMarkdownHandle } from "mdast-util-to-markdown";
import {
  DendronASTDest,
  DendronASTTypes,
  WikiLinkDataV4,
  WikiLinkNoteV4,
} from "../types";
import { MDUtilsV5, ProcMode } from "../utilsv5";
import { addError, getNoteOrError, LinkUtils } from "./utils";

export const LINK_REGEX = /^\[\[([^\]\n]+)\]\]/;
/**
 * Does not require wiki link be the start of the word
 */
export const LINK_REGEX_LOOSE = /\[\[([^\]\n]+)\]\]/;

const parseWikiLink = (linkMatch: string) => {
  linkMatch = NoteUtils.normalizeFname(linkMatch);
  return LinkUtils.parseLinkV2({ linkString: linkMatch });
};

export const matchWikiLink = (text: string) => {
  const match = LINK_REGEX_LOOSE.exec(text);
  if (match) {
    const start = match.index;
    const end = match.index + match[0].length;
    const linkMatch = match[1].trim();
    const link = parseWikiLink(linkMatch);
    return { link, start, end };
  }
  return false;
};

type PluginOpts = CompilerOpts;

type CompilerOpts = {
  convertObsidianLinks?: boolean;
  useId?: boolean;
  prefix?: string;
  convertLinks?: boolean;
};

function normalizeSpaces(link: string) {
  return link.replace(/ /g, "%20");
}

// Character codes
const codes = {
  leftSquareBracket: 91,    // [
  rightSquareBracket: 93,   // ]
  backslash: 92,            // \
  newline: 10,              // \n
  carriageReturn: 13,       // \r
};

/**
 * Micromark syntax extension for wikilinks
 * This defines how to tokenize [[wikilink]] syntax
 */
function createWikiLinkSyntax(): MicromarkExtension {
  const tokenizeWikiLink: Tokenizer = function (effects: Effects, ok: State, nok: State) {
    let content = "";

    const start: State = function (code: Code): State | undefined {
      // Must start with [
      if (code !== codes.leftSquareBracket) {
        return nok(code);
      }
      effects.enter("wikiLink" as any);
      effects.enter("wikiLinkMarker" as any);
      effects.consume(code);
      return openBracket;
    };

    const openBracket: State = function (code: Code): State | undefined {
      // Must be followed by another [
      if (code !== codes.leftSquareBracket) {
        return nok(code);
      }
      effects.consume(code);
      effects.exit("wikiLinkMarker" as any);
      effects.enter("wikiLinkData" as any);
      return insideLink;
    };

    const insideLink: State = function (code: Code): State | undefined {
      // End of file or newline - invalid
      if (code === null || code === codes.newline || code === codes.carriageReturn) {
        return nok(code);
      }
      // Check for closing ]]
      if (code === codes.rightSquareBracket) {
        effects.exit("wikiLinkData" as any);
        effects.enter("wikiLinkMarker" as any);
        effects.consume(code);
        return closeBracket;
      }
      // Consume the character and add to content
      effects.consume(code);
      content += String.fromCharCode(code);
      return insideLink;
    };

    const closeBracket: State = function (code: Code): State | undefined {
      // Must be followed by another ]
      if (code !== codes.rightSquareBracket) {
        // Not a valid wikilink, backtrack
        return nok(code);
      }
      effects.consume(code);
      effects.exit("wikiLinkMarker" as any);
      effects.exit("wikiLink" as any);
      return ok(code);
    };

    return start;
  };

  return {
    text: {
      [codes.leftSquareBracket]: {
        tokenize: tokenizeWikiLink,
        resolveAll: undefined,
      },
    },
  };
}

// Store processor reference for fromMarkdown handler
let currentProcessor: Processor | undefined;

/**
 * mdast-util-from-markdown extension
 * This converts micromark tokens to mdast nodes
 */
function createFromMarkdownExtension(): FromMarkdownExtension {
  const enterWikiLink: Handle = function (token) {
    this.enter(
      {
        type: DendronASTTypes.WIKI_LINK as any,
        value: "",
        data: {} as any,
      } as any,
      token
    );
  };

  const exitWikiLinkData: Handle = function (token) {
    // Get the raw content from the token using sliceSerialize
    const linkContent = this.sliceSerialize(token);
    
    // DEBUG: Log token content
    // console.log("[wikiLinks.exitWikiLinkData] Token content", {
    //   linkContent,
    //   tokenType: token.type,
    //   tokenStart: token.start,
    //   tokenEnd: token.end,
    // });
    
    const node = this.stack[this.stack.length - 1] as unknown as WikiLinkNoteV4;

    // Parse the link content
    try {
      const linkMatch = linkContent.trim();
      const normalizedLink = NoteUtils.normalizeFname(linkMatch);
      const parsed = LinkUtils.parseLinkV2({
        linkString: normalizedLink,
        explicitAlias: true,
      });

      if (parsed) {
        let value = parsed.value;

        // Handle same-file block reference
        if (!value && currentProcessor) {
          const pOpts = MDUtilsV5.getProcOpts(currentProcessor);
          if (pOpts.mode !== ProcMode.NO_DATA) {
            const procData = MDUtilsV5.getProcData(currentProcessor);
            const { fname } = procData;
            if (fname) {
              value = _.trim(NoteUtils.normalizeFname(fname));
            }
          }
        }

        node.value = value || "";
        node.data = {
          alias: parsed.alias || value || "",
          anchorHeader: parsed.anchorHeader,
          vaultName: parsed.vaultName,
          sameFile: parsed.sameFile,
        } as WikiLinkDataV4;
      }
    } catch {
      // Broken link, leave as empty
      node.value = linkContent;
      node.data = {
        alias: linkContent,
      } as WikiLinkDataV4;
    }
  };

  const exitWikiLink: Handle = function (token) {
    this.exit(token);
  };

  return {
    enter: {
      wikiLink: enterWikiLink,
    },
    exit: {
      wikiLinkData: exitWikiLinkData,
      wikiLink: exitWikiLink,
    },
  };
}

/**
 * mdast-util-to-markdown extension
 * This converts mdast nodes back to markdown
 */
function createToMarkdownExtension(proc: Processor, opts?: CompilerOpts): ToMarkdownExtension {
  const copts = _.defaults(opts || {}, {
    convertObsidianLinks: false,
    useId: false,
  });

  const handleWikiLink: ToMarkdownHandle = function (node, _parent, _state, _info) {
    const wikiNode = node as unknown as WikiLinkNoteV4;
    const pOpts = MDUtilsV5.getProcOpts(proc);
    const data = wikiNode.data;
    let value = wikiNode.value;
    const { anchorHeader } = data;

    if (pOpts.mode === ProcMode.NO_DATA) {
      const link = value;
      const calias = data.alias !== value ? `${data.alias}|` : "";
      const anchor = anchorHeader ? `#${anchorHeader}` : "";
      const vaultPrefix = data.vaultName
        ? `${CONSTANTS.DENDRON_DELIMETER}${data.vaultName}/`
        : "";
      return `[[${calias}${vaultPrefix}${link}${anchor}]]`;
    }

    const { dest, noteCacheForRenderDict, vaults, config } =
      MDUtilsV5.getProcData(proc);

    let alias = data.alias;

    const shouldApplyPublishingRules =
      MDUtilsV5.shouldApplyPublishingRules(proc);
    const enableNoteTitleForLink = ConfigUtils.getEnableNoteTitleForLink(
      config,
      shouldApplyPublishingRules
    );

    if (
      dest !== DendronASTDest.MD_DENDRON &&
      enableNoteTitleForLink &&
      !data.alias
    ) {
      if (noteCacheForRenderDict) {
        const targetVault = data.vaultName
          ? VaultUtils.getVaultByName({ vname: data.vaultName, vaults })
          : undefined;

        const target = NoteDictsUtils.findByFname({
          fname: value,
          noteDicts: noteCacheForRenderDict,
          vault: targetVault,
        })[0];

        if (target) {
          alias = target.title;
        }
      }
    }

    // if converting back to dendron md, no further processing
    if (dest === DendronASTDest.MD_DENDRON) {
      return LinkUtils.renderNoteLink({
        link: {
          from: {
            fname: value,
            alias,
            anchorHeader: data.anchorHeader,
            vaultName: data.vaultName,
          },
          data: {
            xvault: !_.isUndefined(data.vaultName),
          },
          type: LinkUtils.astType2DLinkType(DendronASTTypes.WIKI_LINK),
          position: wikiNode.position as Position,
        },
        dest,
      });
    }

    if (copts.useId && dest === DendronASTDest.HTML) {
      let notes;
      const { noteCacheForRenderDict } = MDUtilsV5.getProcData(proc);
      if (noteCacheForRenderDict) {
        notes = NoteDictsUtils.findByFname({
          fname: alias || value,
          noteDicts: noteCacheForRenderDict,
        });
      } else {
        return "error - no note cache provided";
      }

      const { error, note } = getNoteOrError(notes, value);
      if (error) {
        addError(proc, error);
        return "error with link";
      } else {
        value = note!.id;
      }
    }

    const aliasToUse = alias ?? value;
    switch (dest) {
      case DendronASTDest.MD_REGULAR: {
        return `[${aliasToUse}](${copts.prefix || ""}${normalizeSpaces(
          value
        )})`;
      }
      case DendronASTDest.HTML: {
        return `[${aliasToUse}](${copts.prefix || ""}${value}.html${
          data.anchorHeader ? "#" + data.anchorHeader : ""
        })`;
      }
      default:
        return `unhandled case: ${dest}`;
    }
  };

  return {
    handlers: {
      [DendronASTTypes.WIKI_LINK]: handleWikiLink,
    } as any,
  };
}

/**
 * Remark plugin for wikilinks using new micromark architecture
 */
const plugin: Plugin<[CompilerOpts?]> = function (
  this: Processor,
  opts?: PluginOpts
) {
  const proc = this;
  const data = proc.data();

  // Store processor reference for fromMarkdown handler
  currentProcessor = proc;

  // Add micromark syntax extension
  const micromarkExtensions = (data.micromarkExtensions as MicromarkExtension[]) || [];
  micromarkExtensions.push(createWikiLinkSyntax());
  data.micromarkExtensions = micromarkExtensions;

  // Add fromMarkdown extension
  const fromMarkdownExtensions = (data.fromMarkdownExtensions as FromMarkdownExtension[]) || [];
  fromMarkdownExtensions.push(createFromMarkdownExtension());
  data.fromMarkdownExtensions = fromMarkdownExtensions;

  // Add toMarkdown extension (for stringification)
  const toMarkdownExtensions = (data.toMarkdownExtensions as ToMarkdownExtension[]) || [];
  toMarkdownExtensions.push(createToMarkdownExtension(proc, opts));
  data.toMarkdownExtensions = toMarkdownExtensions;
};

export { plugin as wikiLinks };
export { PluginOpts as WikiLinksOpts };
