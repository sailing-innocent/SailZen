/**
 * @file astLatexTransformer.ts
 * @brief AST-based LaTeX code generation for SailZen Doc Engine
 * @description Replaces regex-driven markdown→LaTeX conversion with a robust
 *   recursive MDAST traversal. Supports all standard markdown nodes plus
 *   SailZen custom nodes (cite, figure, table, math env, algorithm, if-format).
 */

import {
  DocProfile,
  NotePropsByIdDict,
  ResolvedAsset,
} from "@saili/common-all";
import { escapeLatex, escapeLatexInlineCode } from "./latexUtils";
// Local constants to avoid importing @saili/unified (which transitively pulls in ESM-only deps)
const SAILZEN_CITE = "sailzenCite";
const SAILZEN_FIGURE = "sailzenFigure";
const SAILZEN_TABLE = "sailzenTable";
const SAILZEN_MATH_ENV = "sailzenMathEnv";
const SAILZEN_ALGORITHM = "sailzenAlgorithm";
const SAILZEN_IF_FORMAT = "sailzenIfFormat";
const WIKI_LINK = "wikiLink";
const REF_LINK_V2 = "refLinkV2";
import type { Node, Parent, Root, Table, TableRow, TableCell } from "mdast";

// ============================================================================
// Context passed through the recursive transformer
// ============================================================================

type TransformContext = {
  profile: DocProfile;
  notesById: NotePropsByIdDict;
  assetMap: Map<string, ResolvedAsset>;
  bibFile: string;
};

// ============================================================================
// Public API
// ============================================================================

export function mdastToLatex(
  tree: Node,
  profile: DocProfile,
  notesById: NotePropsByIdDict,
  bibFile?: string
): string {
  const assetMap = new Map<string, ResolvedAsset>();
  for (const asset of profile.resolvedAssets || []) {
    assetMap.set(asset.ref, asset);
  }
  const ctx: TransformContext = {
    profile,
    notesById,
    assetMap,
    bibFile: bibFile || "ref",
  };
  return transformNode(tree, ctx);
}

// ============================================================================
// Node dispatcher
// ============================================================================

function transformNode(node: Node, ctx: TransformContext): string {
  switch (node.type) {
    case "root":
      return transformRoot(node as Root, ctx);
    case "paragraph":
      return transformParagraph(node as Parent, ctx);
    case "heading":
      return transformHeading(node as any, ctx);
    case "text":
      return escapeLatex((node as any).value || "");
    case "emphasis":
      return `\\textit{${transformChildren(node as Parent, ctx)}}`;
    case "strong":
      return `\\textbf{${transformChildren(node as Parent, ctx)}}`;
    case "inlineCode":
      return `\\texttt{${escapeLatexInlineCode((node as any).value || "")}}`;
    case "code":
      return transformCode(node as any, ctx);
    case "blockquote":
      return `\\begin{quote}\n${transformChildren(node as Parent, ctx)}\n\\end{quote}`;
    case "list":
      return transformList(node as any, ctx);
    case "listItem":
      return `\\item ${transformChildren(node as Parent, ctx)}`;
    case "table":
      return transformTable(node as Table, ctx);
    case "thematicBreak":
      return "\\hrulefill\n";
    case "link":
      return transformLink(node as any, ctx);
    case "image":
      return transformImage(node as any, ctx);
    case "break":
      return "\\newline\n";
    case "footnoteReference":
      return `\\footnote{${escapeLatex((node as any).label || "")}}`;
    case "footnoteDefinition":
      return ""; // Definitions are inline-replaced by footnoteReference
    case "html":
      return (node as any).value || "";
    case "yaml":
      return ""; // Frontmatter is handled separately

    // SailZen custom nodes
    case SAILZEN_CITE:
      return transformCite(node as any);
    case SAILZEN_FIGURE:
      return transformFigure(node as any, ctx);
    case SAILZEN_TABLE:
      return transformSailzenTable(node as any, ctx);
    case SAILZEN_MATH_ENV:
      return transformMathEnv(node as any, ctx);
    case SAILZEN_ALGORITHM:
      return transformAlgorithm(node as any, ctx);
    case SAILZEN_IF_FORMAT:
      return transformIfFormat(node as any, ctx);
    case WIKI_LINK:
      return transformWikiLink(node as any);
    case REF_LINK_V2:
      return ""; // Should be expanded by assembler before reaching here

    default:
      // For unknown nodes, try to render children
      if ("children" in node && Array.isArray((node as Parent).children)) {
        return transformChildren(node as Parent, ctx);
      }
      return "";
  }
}

function transformChildren(parent: Parent, ctx: TransformContext): string {
  if (!parent.children) return "";
  return parent.children.map((child) => transformNode(child, ctx)).join("");
}

// ============================================================================
// Standard markdown nodes
// ============================================================================

function transformRoot(root: Root, ctx: TransformContext): string {
  return root.children
    .map((child) => transformNode(child, ctx))
    .filter(Boolean)
    .join("\n\n");
}

function transformParagraph(para: Parent, ctx: TransformContext): string {
  const inner = transformChildren(para, ctx);
  if (!inner.trim()) return "";
  return inner;
}

function transformHeading(node: any, ctx: TransformContext): string {
  const level = node.depth || 1;
  const cmd =
    level === 1
      ? "section"
      : level === 2
        ? "subsection"
        : level === 3
          ? "subsubsection"
          : "paragraph";
  const title = transformChildren(node as Parent, ctx);
  return `\\${cmd}{${title}}`;
}

function transformCode(node: any, _ctx: TransformContext): string {
  const lang = node.lang || "";
  const value = node.value || "";
  if (lang === "latex") {
    return value; // Passthrough raw LaTeX
  }
  return `\\begin{verbatim}\n${value}\n\\end{verbatim}`;
}

function transformList(node: any, ctx: TransformContext): string {
  const env = node.ordered ? "enumerate" : "itemize";
  const items = (node.children || [])
    .map((child: Node) => transformNode(child, ctx))
    .join("\n");
  return `\\begin{${env}}\n${items}\n\\end{${env}}`;
}

function transformTable(table: Table, ctx: TransformContext): string {
  if (!table.children || table.children.length < 2) return "";

  const rows = table.children as TableRow[];
  const headerRow = rows[0];
  const sepRow = rows[1];
  const bodyRows = rows.slice(2);

  // Determine alignment from separator row
  const aligns = (sepRow.children || []).map((cell: TableCell) => {
    const text = cell.children
      ?.map((c: any) => c.value || "")
      .join("")
      .trim();
    if (text?.startsWith(":") && text?.endsWith(":")) return "c";
    if (text?.endsWith(":")) return "r";
    return "l";
  });

  const colCount = Math.max(
    headerRow.children?.length || 0,
    aligns.length
  );
  const colSpec = aligns.slice(0, colCount).join("") || "l".repeat(colCount);

  let latex = `\\begin{tabular}{${colSpec}}\n\\hline\n`;
  latex += formatTableRow(headerRow, ctx) + " \\\\\n\\hline\n";
  for (const row of bodyRows) {
    latex += formatTableRow(row, ctx) + " \\\\\n";
  }
  latex += "\\hline\n\\end{tabular}";
  return latex;
}

function formatTableRow(row: TableRow, ctx: TransformContext): string {
  return (row.children || [])
    .map((cell: TableCell) =>
      escapeLatex(
        cell.children?.map((c: any) => transformNode(c, ctx)).join("") || ""
      )
    )
    .join(" & ");
}

function transformLink(node: any, ctx: TransformContext): string {
  const url = node.url || "";
  const text = transformChildren(node as Parent, ctx);
  return `\\href{${url}}{${text}}`;
}

function transformImage(node: any, _ctx: TransformContext): string {
  const url = node.url || "";
  const alt = node.alt || "";
  return `\\includegraphics{${url}} % ${alt}`;
}

function transformWikiLink(node: any): string {
  const value = node.value || "";
  const alias = node.data?.alias || value;
  const anchor = node.data?.anchorHeader;
  if (anchor) {
    return `${escapeLatex(alias)}~(\\ref{${anchor}})`;
  }
  return escapeLatex(alias);
}

// ============================================================================
// SailZen custom nodes
// ============================================================================

function transformCite(node: any): string {
  const keys = node.keys || [];
  if (keys.length === 0) return "";
  return `\\cite{${keys.join(", ")}}`;
}

function transformFigure(node: any, ctx: TransformContext): string {
  const src = node.src || "";
  const caption = node.caption || "";
  const options = node.options || {};

  const asset = ctx.assetMap.get(src);
  const fileName = asset?.path
    ? asset.path.replace(/\\/g, "/").split("/").pop() || src
    : src;
  const latexPath = `../figures/${fileName}`;
  const figCaption = caption || asset?.caption || "";
  const figLabel = options.label || asset?.label || `fig:${src}`;
  const width = options.width || asset?.width || "0.8\\textwidth";
  const placement = options.placement || "htbp";

  return `\\begin{figure}[${placement}]
  \\centering
  \\includegraphics[width=${width}]{${latexPath}}
  \\caption{${escapeLatex(figCaption)}}
  \\label{${figLabel}}
\\end{figure}`;
}

function transformSailzenTable(node: any, ctx: TransformContext): string {
  const caption = node.caption || "";
  const label = node.label || "";
  const tableNode = node.table;

  let tabular = "";
  if (tableNode) {
    tabular = transformTable(tableNode as Table, ctx);
  }

  return `\\begin{table}[htbp]
\\centering
\\caption{${escapeLatex(caption)}}${label ? `\\label{${label}}` : ""}
${tabular}
\\end{table}`;
}

function transformMathEnv(node: any, ctx: TransformContext): string {
  const envType = node.envType || "theorem";
  const title = node.title || "";
  const label = node.label || "";
  const inner = transformChildren(node as Parent, ctx);

  const labelPart = label ? `\\label{${label}}` : "";
  const titlePart = title ? `[${escapeLatex(title)}]` : "";

  return `\\begin{${envType}}${titlePart}${labelPart}
${inner}
\\end{${envType}}`;
}

function transformAlgorithm(node: any, ctx: TransformContext): string {
  const title = node.title || "";
  const label = node.label || "";
  const labelPart = label ? `\\label{${label}}` : "";

  let inner = transformChildren(node as Parent, ctx);

  // Handle ::input and ::output within algorithm content
  inner = inner.replace(/::input\[([^\]]*)\]/g, (_m: string, inp: string) =>
    `\\Require ${inp}`
  );
  inner = inner.replace(/::output\[([^\]]*)\]/g, (_m: string, out: string) =>
    `\\Ensure ${out}`
  );
  // Numbered/bullet steps -> \State
  inner = inner.replace(
    /^(\d+)\.\s+(.+)$/gm,
    (_m: string, _num: string, step: string) => `\\State ${step}`
  );
  inner = inner.replace(/^-\s+(.+)$/gm, (_m: string, step: string) =>
    `\\State ${step}`
  );
  // Indented lines as continuation
  inner = inner.replace(/^[ \t]+(.+)$/gm, (_m: string, line: string) =>
    `  ${line}`
  );

  return `\\begin{algorithm}[htbp]
\\caption{${escapeLatex(title)}}${labelPart}
\\begin{algorithmic}
${inner}
\\end{algorithmic}
\\end{algorithm}`;
}

function transformIfFormat(node: any, ctx: TransformContext): string {
  const format = node.format || "";
  if (format !== "latex") return "";
  return transformChildren(node as Parent, ctx);
}


