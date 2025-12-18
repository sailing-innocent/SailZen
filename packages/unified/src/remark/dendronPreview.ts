import { vault2Path } from "@saili/common-all";
import _ from "lodash";
import { Image, Link, Text } from "mdast";
import type { Transformer, Processor } from "unified";
import { Node, Parent } from "unist";
import { visit } from "unist-util-visit";
import { VFile } from "vfile";
import { AnchorUtils, RemarkUtils } from ".";
import { DendronASTTypes, HashTag, ZDocTag, WikiLinkNoteV4 } from "../types";
import { MDUtilsV5 } from "../utilsv5";
import { URI, Utils } from "vscode-uri";

type PluginOpts = {};

/** Makes the `.url` of the given image note a full path. */
export function makeImageUrlFullPath({
  proc,
  node,
}: {
  proc: Processor;
  node: Image;
}) {
  // ignore web images
  if (_.some(["http://", "https://"], (ent) => node.url.startsWith(ent))) {
    return;
  }
  // assume that the path is relative to vault
  const { wsRoot, vault } = MDUtilsV5.getProcData(proc);
  const uri = Utils.joinPath(
    vault2Path({ wsRoot: URI.file(wsRoot), vault }),
    decodeURI(node.url)
  );
  node.url = uri.fsPath;
}

/**
 * Transforms any wiklinks into a vscode command URI for gotoNote.
 */
function modifyWikilinkValueToCommandUri({
  proc,
  node,
}: {
  proc: Processor;
  node: WikiLinkNoteV4;
}) {
  const { vault } = MDUtilsV5.getProcData(proc);

  const anchor = node.data.anchorHeader
    ? AnchorUtils.string2anchor(node.data.anchorHeader)
    : undefined;

  const qs = node.value;
  const goToNoteCommandOpts = {
    qs,
    vault,
    anchor,
  };
  const encodedArgs = encodeURIComponent(JSON.stringify(goToNoteCommandOpts));
  node.data.alias = node.data.alias || qs;
  node.value = `command:dendron.gotoNote?${encodedArgs}`;
}

/**
 * Transforms any ZDocTag or HashTag nodes into a vscode command URI for gotoNote.
 */
function modifyTagValueToCommandUri({
  proc,
  node,
}: {
  proc: Processor;
  node: ZDocTag | HashTag;
}) {
  const { vault } = MDUtilsV5.getProcData(proc);

  const goToNoteCommandOpts = {
    qs: node.fname,
    vault,
  };

  const encodedArgs = encodeURIComponent(JSON.stringify(goToNoteCommandOpts));

  // Convert the node to a 'link' type so that it can behave properly like a
  // link instead of the tag behavior, since we've changed the value to a
  // command URI
  (node as unknown as Link).type = "link";
  (node as unknown as Link).url = `command:dendron.gotoNote?${encodedArgs}`;

  const childTextNode: Text = {
    type: "text",
    value: node.value,
  };

  (node as unknown as Link).children = [childTextNode];
}

export function dendronHoverPreview(
  this: Processor,
  _opts?: PluginOpts
): Transformer {
  const proc = this;
  function transformer(tree: Node, _file: VFile) {
    visit(
      tree,
      [
        DendronASTTypes.FRONTMATTER,
        DendronASTTypes.IMAGE,
        DendronASTTypes.EXTENDED_IMAGE,
        DendronASTTypes.WIKI_LINK,
        DendronASTTypes.ZDOCTAG,
        DendronASTTypes.HASHTAG,
      ],
      (node: Node, index: number | undefined, parent: Node | undefined) => {
        // Remove the frontmatter because it will break the output
        if (RemarkUtils.isFrontmatter(node) && parent) {
          // Remove this node
          (parent as Parent).children.splice(index!, 1);
          // Since this removes the frontmatter node, the next node to visit is at the same index.
          return index;
        }
        if (RemarkUtils.isImage(node) || RemarkUtils.isExtendedImage(node)) {
          makeImageUrlFullPath({ proc, node });
        } else if (RemarkUtils.isWikiLink(node)) {
          modifyWikilinkValueToCommandUri({ proc, node });
        } else if (RemarkUtils.isZDocTag(node) || RemarkUtils.isHashTag(node)) {
          modifyTagValueToCommandUri({ proc, node });
        }
        return undefined; // continue
      }
    );
  }
  return transformer;
}

export { PluginOpts as DendronPreviewOpts };
