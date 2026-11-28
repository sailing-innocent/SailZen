import {
  SailConfig,
  DNoteRefLink,
  DNoteRefLinkRaw,
  DVault,
  NoteProps,
  SailASTDest,
} from "@saili/common-all";
import { Heading, Image, Parent, Root } from "mdast";
import { Processor } from "unified";
import type { Node as UnistNode } from "unist";
import { SailPubOpts } from "./remark/sailPub";
import { WikiLinksOpts } from "./remark/wikiLinks";

export { Node as UnistNode } from "unist";
export { VFile } from "vfile";
export { Processor };
export { SailASTDest };

// --- General

export type SailASTRoot = Root & {
  children: SailASTNode;
};

export type WikiLinkProps = {
  alias: string;
  value: string;
  anchorHeader?: string;
};

export type SailASTNode = Parent & {
  notes?: NoteProps[];
  children?: Parent["children"] | SailASTNode[];
};

export enum SailASTTypes {
  WIKI_LINK = "wikiLink",
  REF_LINK_V2 = "refLinkV2",
  BLOCK_ANCHOR = "blockAnchor",
  HASHTAG = "hashtag",
  ZDOCTAG = "zdoctag",
  EXTENDED_IMAGE = "extendedImage",
  // SailZen Doc extensions
  SAILZEN_CITE = "sailzenCite",
  SAILZEN_FIGURE = "sailzenFigure",
  SAILZEN_TABLE = "sailzenTable",
  SAILZEN_MATH_ENV = "sailzenMathEnv",
  SAILZEN_ALGORITHM = "sailzenAlgorithm",
  SAILZEN_IF_FORMAT = "sailzenIfFormat",
  /** Page element marker, e.g. `$$PREFIX$$`. See remark/pageElements. */
  PAGE_ELEMENT = "pageElement",
  // Not sail-specific, included here for convenience
  ROOT = "root",
  HEADING = "heading",
  LIST = "list",
  LIST_ITEM = "listItem",
  PARAGRAPH = "paragraph",
  TEXT = "text",
  TABLE = "table",
  TABLE_ROW = "tableRow",
  TABLE_CELL = "tableCell",
  IMAGE = "image",
  FRONTMATTER = "yaml",
  LINK = "link",
  CODE = "code",
  INLINE_CODE = "inlineCode",
  FOOTNOTE_DEFINITION = "footnoteDefinition",
  FOOTNOTE_REFERENCE = "footnoteReference",
  HTML = "html",
  YAML = "yaml",
}

export enum VaultMissingBehavior {
  FALLBACK_TO_ORIGINAL_VAULT,
  THROW_ERROR,
}

export type SailASTData = {
  dest: SailASTDest;
  vault: DVault;
  fname: string;
  wikiLinkOpts?: WikiLinksOpts;
  config: SailConfig;
  overrides?: Partial<SailPubOpts>;
  shouldApplyPublishRules?: boolean;
  /**
   * Inidicate that we are currently inside a note ref
   */
  insideNoteRef?: boolean;
};

// --- NODES

export type WikiLinkNoteV4 = Omit<SailASTNode, "children"> & {
  type: SailASTTypes.WIKI_LINK;
  value: string;
  data: WikiLinkDataV4;
};

export type WikiLinkDataV4 = {
  alias: string;
  anchorHeader?: string;
  prefix?: string;
  vaultName?: string;
  /** Denotes a same file link, for example `[[#anchor]]` */
  sameFile?: boolean;
};

export type RehypeLinkData = WikiLinkDataV4 & {
  hName: string;
};

export type NoteRefNoteV4 = Omit<SailASTNode, "children"> & {
  type: SailASTTypes.REF_LINK_V2;
  value: string;
  data: NoteRefDataV4;
};

export type NoteRefNoteRawV4 = Omit<SailASTNode, "children"> & {
  type: SailASTTypes.REF_LINK_V2;
  value: string;
  data: NoteRefDataRawV4;
};

export type NoteRefDataV4 = {
  link: DNoteRefLink;
  vaultName?: string;
};

export type NoteRefDataRawV4 = {
  link: DNoteRefLinkRaw;
  vaultName?: string;
};

export type BlockAnchor = SailASTNode & {
  type: SailASTTypes.BLOCK_ANCHOR;
  id: string;
};

/** Hashtag tags, like `#foo.bar`, a shorthand for `[[tags.foo.bar]]` */
export type HashTag = SailASTNode & {
  type: SailASTTypes.HASHTAG;
  /** The fname that the hashtag actually references, like `tags.foo.bar` */
  fname: string;
  /** The full test of the hashtag, like `#foo.bar` */
  value: string;
};

/** User tags, like `@Hamilton.Margaret`, a shorthand for `[[user.Hamilton.Margaret]]` */
export type ZDocTag = SailASTNode & {
  type: SailASTTypes.ZDOCTAG;
  /** The fname that the hashtag actually references, like `user.Hamilton.Margaret` */
  fname: string;
  /** The full test of the hashtag, like `@Hamilton.Margaret` */
  value: string;
};

export type Anchor = BlockAnchor | Heading;

export type ExtendedImage = SailASTNode &
  Image & {
    /** User provided props, to set things like width and height. */
    props: { [key: string]: any };
  };

// --- SailZen Doc AST Nodes

/** Citation node: ::cite[key1, key2] */
export type SailZenCite = SailASTNode & {
  type: SailASTTypes.SAILZEN_CITE;
  keys: string[];
};

/** Figure node: ::figure[caption](src){opts} */
export type SailZenFigure = SailASTNode & {
  type: SailASTTypes.SAILZEN_FIGURE;
  caption: string;
  src: string;
  options: Record<string, any>;
};

/** Table node: ::table[caption](label){opts} ... markdown table ... ::end */
export type SailZenTable = SailASTNode & {
  type: SailASTTypes.SAILZEN_TABLE;
  caption: string;
  label: string;
  options: Record<string, any>;
  table?: any; // mdast Table node
};

/** Math environment node: ::theorem, ::proof, ::definition */
export type SailZenMathEnv = SailASTNode & {
  type: SailASTTypes.SAILZEN_MATH_ENV;
  envType: "theorem" | "proof" | "definition" | "lemma" | "corollary" | "proposition" | "remark";
  title?: string;
  label?: string;
};

/** Algorithm node: ::algorithm */
export type SailZenAlgorithm = SailASTNode & {
  type: SailASTTypes.SAILZEN_ALGORITHM;
  title: string;
  label?: string;
  children?: UnistNode[];
};

/** Conditional format node: ::if-format[latex] ... ::end */
export type SailZenIfFormat = SailASTNode & {
  type: SailASTTypes.SAILZEN_IF_FORMAT;
  format: string;
  children?: UnistNode[];
};

/** Page element marker node: `<sail-elem key="PREFIX" />`.
 * Content is resolved at render time via the page element registry; see
 * `remark/pageElements`. */
export type PageElement = SailASTNode & {
  type: SailASTTypes.PAGE_ELEMENT;
  /** Registered provider key, e.g. "PREFIX". */
  key: string;
  /** Parsed marker arguments. */
  args: import("./remark/pageElements/types").PageElementArgs;
  /** Original marker text, used for lossless markdown round-trips. */
  raw: string;
};
