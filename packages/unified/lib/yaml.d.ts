import { Literal, MappingItem, Node as YamlUnistNode, Parent as YamlUnistParent, Plain, QuoteDouble, QuoteSingle } from "yaml-unist-parser";
import type { YAML } from "mdast";
export declare function isYamlUnistParent(node: any): node is YamlUnistParent;
export declare function isMappingItem(node: any): node is MappingItem;
export declare function isPlain(node: any): node is Plain;
export declare function isQuoteSingle(node: any): node is QuoteSingle;
export declare function isQuoteDouble(node: any): node is QuoteDouble;
export declare function isYamlString(node: any): node is Literal;
/** `unist-util-visit`, kind of, but for YamlUnist.
 *
 * The reason this is duplicated here is that even though YamlUnist is
 * technically Unist compatible, the types don't match so we can't use the unist
 * function.
 */
export declare function visitYamlUnist(node: YamlUnistNode | YamlUnistNode[], visitor: (node: YamlUnistNode) => boolean | undefined | void | null): void;
/** Get the mapping items (`key: value`) from the frontmatter. */
export declare function parseFrontmatter(frontmatter: YAML | string): MappingItem[];
export declare function getFrontmatterTags(frontmatter: MappingItem[]): Literal[];
