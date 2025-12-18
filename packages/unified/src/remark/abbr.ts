import type { Plugin, Processor } from "unified";
import { Element } from "hast";
import { html } from "mdast-builder";
import { visit } from "unist-util-visit";
import type { Text, Root, Node } from "mdast";
import { toString } from "mdast-util-to-string";
// @ts-ignore - Eat type is not exported from remark-parse
type Eat = any;

/**
 * Plugin options for remark-abbr replacement
 */
type PluginOpts = {
  /** When set to true, the first occurrence of each abbreviation is expanded in place */
  expandFirst?: boolean;
};

/**
 * Abbreviation definition regex: *[ABBR]: Full Expansion
 */
const ABBR_DEFINITION_REGEX = /^\*\[([^\]]+)\]:\s*(.+)$/;

/**
 * Abbreviation usage regex: matches abbreviations in text (2+ uppercase letters)
 */
const ABBR_USAGE_REGEX = /\b([A-Z]{2,})\b/g;

/**
 * Map to store abbreviation definitions: abbr -> expansion
 */
const abbreviations: Map<string, string> = new Map();

const plugin: Plugin<[PluginOpts?]> = function (
  this: Processor,
  _opts?: PluginOpts
) {
  // Reset abbreviations map for each processing
  abbreviations.clear();
  
  attachParser(this);
  
  // Use transform to process AST after parsing
  return (tree: Node) => {
    // First pass: collect all abbreviation definitions from paragraphs
    visit(tree, "paragraph", (node: any) => {
      const text = toString(node);
      const match = ABBR_DEFINITION_REGEX.exec(text);
      if (match) {
        const abbr = match[1].trim();
        const expansion = match[2].trim();
        abbreviations.set(abbr.toUpperCase(), expansion);
      }
    });

    // Second pass: replace abbreviations in text nodes
    if (abbreviations.size > 0) {
      visit(tree, "text", (node: Text, index: number | undefined, parent: any) => {
        if (!parent || index === undefined) return;
        
        const text = node.value;
        const parts: Array<{ type: string; value?: string; data?: any }> = [];
        let lastIndex = 0;
        let match: RegExpExecArray | null;

        // Reset regex lastIndex
        ABBR_USAGE_REGEX.lastIndex = 0;

        while ((match = ABBR_USAGE_REGEX.exec(text)) !== null) {
          const abbr = match[1];
          const expansion = abbreviations.get(abbr);

          if (expansion) {
            // Add text before the match
            if (match.index > lastIndex) {
              parts.push({
                type: "text",
                value: text.slice(lastIndex, match.index),
              });
            }

            // Add the abbreviation as a custom node
            parts.push({
              type: "abbr",
              value: abbr,
              data: {
                hName: "abbr",
                hProperties: {
                  title: expansion,
                },
              },
            });

            lastIndex = match.index + abbr.length;
          }
        }

        // If we found matches, replace the text node
        if (parts.length > 0) {
          // Add remaining text
          if (lastIndex < text.length) {
            parts.push({
              type: "text",
              value: text.slice(lastIndex),
            });
          }

          // Replace the text node with new nodes
          parent.children.splice(index, 1, ...parts);
        }
      });
    }
  };
};

function attachParser(proc: Processor) {
  const Parser = proc.Parser;
  if (!Parser) return;

  // Add block tokenizer for abbreviation definitions (standalone lines)
  const blockTokenizers = Parser.prototype.blockTokenizers;
  const blockMethods = Parser.prototype.blockMethods;

  function blockTokenizer(eat: Eat, value: string, silent?: boolean) {
    const match = ABBR_DEFINITION_REGEX.exec(value);
    if (!match) return false;

    if (silent) return true;

    const abbr = match[1].trim();
    const expansion = match[2].trim();

    // Store the abbreviation definition
    abbreviations.set(abbr.toUpperCase(), expansion);

    // Return a node that will be removed during compilation
    return eat(match[0])({
      type: "abbrDefinition",
      data: {
        hName: "abbr-definition",
        hProperties: {
          abbr: abbr,
          expansion: expansion,
        },
      },
    });
  }

  blockTokenizer.locator = function (value: string, fromIndex: number) {
    return value.indexOf("*[", fromIndex);
  };

  blockTokenizers.abbrDefinition = blockTokenizer;
  blockMethods.splice(blockMethods.indexOf("paragraph"), 0, "abbrDefinition");
}

function attachCompiler(proc: Processor, _opts?: PluginOpts) {
  const Compiler = proc.Compiler;
  if (!Compiler) return;
  const visitors = Compiler.prototype.visitors;

  if (visitors) {
    // Handle abbreviation definitions (don't render them)
    visitors.abbrDefinition = () => {
      return "";
    };

    // Handle abbreviation usage
    visitors.abbr = (node: any): ReturnType<typeof html> => {
      const properties = node.data?.hProperties || {};
      const title = properties.title || "";
      const value = node.value || "";
      return html(`<abbr title="${title.replace(/"/g, "&quot;")}">${value}</abbr>`);
    };
  }
}

export { plugin as abbrPlugin };
export type { PluginOpts as AbbrOpts };
