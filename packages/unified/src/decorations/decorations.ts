import {
  ConfigUtils,
  SailError,
  DEngine,
  Diagnostic,
  GetDecorationsOpts,
  ISailError,
  SailConfig,
  NonOptional,
  NoteProps,
  offsetRange,
} from "@saili/common-all";

import {
  SailASTDest,
  SailASTNode,
  SailASTTypes,
  ZDocTag,
  BlockAnchor,
  HashTag,
  NoteRefNoteV4,
  WikiLinkNoteV4,
} from "../types";

import { decorateHashTag } from "./hashTags";
import { decorateReference } from "./references";
import { decorateZDocTag } from "./zdocTags";
import { decorateWikilink } from "./wikilinks";
import { Decoration, DecoratorIn, DecoratorOut } from "./utils";
import { decorateFrontmatter } from "./frontmatter";
import { decorateBlockAnchor } from "./blockAnchors";
import { MDUtilsV5, ProcMode } from "../utilsv5";
import { FrontmatterContent } from "mdast";
import {
  checkAndWarnBadFrontmatter,
  warnMissingFrontmatter,
} from "./diagnostics";
import _ from "lodash";
import { visit } from "unist-util-visit";
import { MdastUtils } from "..";

/** Dispatches the correct decorator based on the type of AST node. */
function runDecorator(
  opts: DecoratorIn
): DecoratorOut | Promise<DecoratorOut> | undefined {
  const { node } = opts;

  switch (node.type) {
    case SailASTTypes.BLOCK_ANCHOR:
      return decorateBlockAnchor(opts as DecoratorIn<BlockAnchor>);
    case SailASTTypes.HASHTAG:
      return decorateHashTag(opts as DecoratorIn<HashTag>);
    case SailASTTypes.FRONTMATTER:
      return decorateFrontmatter(
        opts as unknown as DecoratorIn<FrontmatterContent>
      );
    case SailASTTypes.ZDOCTAG:
      return decorateZDocTag(opts as DecoratorIn<ZDocTag>);
    case SailASTTypes.WIKI_LINK:
      return decorateWikilink(opts as unknown as DecoratorIn<WikiLinkNoteV4>);
    case SailASTTypes.REF_LINK_V2:
      return decorateReference(opts as unknown as DecoratorIn<NoteRefNoteV4>);
    default:
      return undefined;
  }
}

/** Get all decorations within the visible ranges for given note. */
export async function runAllDecorators(
  opts: Omit<GetDecorationsOpts, "id"> & {
    note: NoteProps;
    engine: DEngine;
    config: SailConfig;
  }
) {
  const { note, ranges, config } = opts;

  const allDecorations: Decoration[] = [];
  const allDiagnostics: Diagnostic[] = [];
  const allErrors: ISailError[] = [];

  const proc = MDUtilsV5.procRemarkParse(
    {
      mode: ProcMode.FULL,
      parseOnly: true,
    },
    {
      dest: SailASTDest.MD_DENDRON,
      vault: note.vault,
      fname: note.fname,
      config,
    }
  );
  const maxNoteLength = ConfigUtils.getWorkspace(config).maxNoteLength;

  for (const { range, text } of ranges) {
    if (text.length > maxNoteLength) {
      return {
        errors: [
          new SailError({
            message: `Stopping decorations because visible range is too large. Unless you have a massive screen or really long lines of text, this may be a bug.`,
            payload: { maxNoteLength, textLength: text.length },
          }),
        ],
      };
    }
    const tree = proc.parse(text);

    // eslint-disable-next-line no-await-in-loop
    await MdastUtils.visitAsync(tree, [], async (nodeIn) => {
      // This was parsed, it must have a position
      const node = nodeIn as NonOptional<SailASTNode, "position">;

      // Need to update node position with the added offset from the range
      const decoratorOut = await runDecorator({
        ...opts,
        node,
        note,
        noteText: text,
      });
      if (decoratorOut) {
        const { decorations, errors } = decoratorOut;
        allDecorations.push(
          ...decorations.map((decoration) => {
            // Add the offset from the start of the range so these decorations match up in the original document
            decoration.range = offsetRange(decoration.range, {
              line: range.start.line,
            });
            return decoration;
          })
        );
        if (errors) allErrors.push(...errors);
      }
    });
  }

  // Check for frontmatter diagnostics. Diagnostics always run on the whole note because they need to be active even when they are not visible.
  let frontmatter: FrontmatterContent | undefined;
  const fullTree = proc.parse(opts.text);
  visit(fullTree as any, ["yaml"], (node: FrontmatterContent) => {
    frontmatter = node;
    return false; // stop iterating
  });
  if (_.isUndefined(frontmatter)) {
    allDiagnostics.push(warnMissingFrontmatter());
  } else {
    const { diagnostics, errors } = checkAndWarnBadFrontmatter(
      note,
      frontmatter
    );
    allDiagnostics.push(...diagnostics);
    if (errors) allErrors.push(...errors);
  }

  return {
    allDecorations,
    allDiagnostics,
    allErrors,
  };
}
