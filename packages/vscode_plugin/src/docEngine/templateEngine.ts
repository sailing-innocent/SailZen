/**
 * @file templateEngine.ts
 * @brief Built-in LaTeX template library and variable injection engine
 * @description Provides a collection of academic paper templates (article, acmart,
 *   cvpr, iccv, icml, njuthesis, arxiv) with handlebars-style variable substitution.
 */

import {
  DocExportConfig,
  DocExportFormat,
  DocProfile,
  DocSection,
  DocTemplateConfig,
} from "@saili/common-all";
import {
  ExternalTemplate,
  listExternalTemplates,
  loadExternalTemplate,
  renderExternalTemplate,
  resolveTemplateDir,
} from "./templateLoader";

// ============================================================================
// Escape helpers (mirrored from latexBackend to avoid circular deps)
// ============================================================================

function escapeLatex(text: string): string {
  return (
    text
      .replace(/\\/g, "\\textbackslash{}")
      .replace(/\{/g, "\\{")
      .replace(/\}/g, "\\}")
      .replace(/\$/g, "\\$")
      .replace(/&/g, "\\&")
      .replace(/#/g, "\\#")
      .replace(/\^/g, "\\^{}")
      .replace(/_/g, "\\_")
      .replace(/%/g, "\\%")
      .replace(/~/g, "\\textasciitilde{}")
  );
}

function formatAuthors(authors: any[]): string {
  if (!authors || authors.length === 0) return "";
  return authors
    .map((a) => {
      const name = escapeLatex(a.name || "");
      const aff = a.affiliation ? ` \\\\ ${escapeLatex(a.affiliation)}` : "";
      const email = a.email ? ` \\\\ \texttt{${escapeLatex(a.email)}}` : "";
      return `\\author{${name}${aff}${email}}`;
    })
    .join("\n");
}

function formatAcmAuthors(authors: any[]): string {
  if (!authors || authors.length === 0) return "";
  return authors
    .map((a) => {
      const name = escapeLatex(a.name || "");
      const institution = escapeLatex(a.institution || a.affiliation || "");
      const country = escapeLatex(a.country || "USA");
      const email = a.email ? escapeLatex(a.email) : "";
      let block = `\\author{${name}}`;
      if (institution) {
        block += `\n\\affiliation{%\n  \\institution{${institution}}\n  \\country{${country}}\n}`;
      }
      if (email) {
        block += `\n\\email{${email}}`;
      }
      return block;
    })
    .join("\n");
}
function formatKeywords(keywords: string[]): string {
  if (!keywords || keywords.length === 0) return "";
  return `\\keywords{${keywords.map(escapeLatex).join("; ")}}`;
}

// ============================================================================
// Template variable resolution
// ============================================================================

export function resolveTemplateVars(
  profile: DocProfile,
  exportConfig: DocExportConfig
): Record<string, any> {
  const meta = profile.meta || {};
  const vars = exportConfig.vars || {};

  return {
    // Standard frontmatter fallbacks
    title: meta.title || profile.rootNoteFname,
    authors: meta.authors || [],
    abstract: meta.abstract || "",
    keywords: meta.keywords || [],
    conference: meta.conference || "",
    journal: meta.journal || "",
    doi: meta.doi || "",
    year: meta.year || new Date().getFullYear(),
    // User-supplied vars override everything
    ...vars,
  };
}

// ============================================================================
// Built-in template definitions
// ============================================================================

export type BuiltinTemplate = DocTemplateConfig & {
  engine: "pdflatex" | "xelatex" | "lualatex" | "typst";
  packages?: string[];
  renderMain: (
    vars: Record<string, any>,
    body: string,
    options?: { splitSections?: boolean; sections?: DocSection[] }
  ) => string;
};

const COMMON_PACKAGES = [
  "graphicx",
  "amsmath",
  "amsthm",
  "hyperref",
  "listings",
  "xcolor",
  "booktabs",
  "multirow",
  "algorithm",
  "algorithmic",
  "cleveref",
];

function buildPreamble(packages: string[], extra?: string): string {
  const pkgLines = packages.map((p) => `\\usepackage{${p}}`).join("\n");
  return `${pkgLines}${extra ? "\n" + extra : ""}`;
}

function buildBodyContent(
  body: string,
  options?: { splitSections?: boolean; sections?: DocSection[] },
  format: DocExportFormat = "latex"
): string {
  if (options?.splitSections && options?.sections && options.sections.length > 0) {
    if (format === "typst") {
      return options.sections.map((s) => `#include "sections/${s.fileName}"`).join("\n\n");
    }
    return options.sections.map((s) => `\\input{sections/${s.fileName}}`).join("\n\n");
  }
  return body;
}

export const BUILTIN_TEMPLATES: Record<string, BuiltinTemplate> = {
  article: {
    id: "article",
    format: "latex",
    description: "Basic article template with Chinese support (ctex)",
    engine: "xelatex",
    requires: [],
    packages: [...COMMON_PACKAGES, "ctex"],
    variables: [
      { name: "title", required: true },
      { name: "authors", type: "array", default: [] },
      { name: "abstract", type: "string" },
      { name: "keywords", type: "array", default: [] },
      { name: "bibliography", default: "ref" },
      { name: "bibliographystyle", default: "plain" },
      { name: "documentclass", default: "article" },
      { name: "documentclass_options", default: "" },
    ],
    sectioning: { style: "numbered", maxDepth: 3 },
    renderMain(vars, body, options) {
      const docClass = vars.documentclass || "article";
      const docOpts = vars.documentclass_options ? `[${vars.documentclass_options}]` : "";
      const authors = formatAuthors(vars.authors);
      const abstract = vars.abstract
        ? `\\begin{abstract}\n${vars.abstract}\n\\end{abstract}`
        : "";
      const keywords = (vars.keywords || []).length
        ? `\\textbf{Keywords:} ${vars.keywords.map(escapeLatex).join(", ")}`
        : "";
      const bibStyle = vars.bibliographystyle || "plain";
      const bibFile = vars.bibliography || "ref";
      const bodyContent = buildBodyContent(body, options, "latex");

      return `\\documentclass${docOpts}{${docClass}}
\\usepackage[UTF8]{ctex}
${buildPreamble(this.packages || [])}

\\title{${escapeLatex(vars.title || "Untitled")}}
${authors}

\\begin{document}
\\maketitle
${abstract}
${keywords}

${bodyContent}

\\bibliographystyle{${bibStyle}}
\\bibliography{${bibFile}}
\\end{document}
`;
    },
  },
  "research-article": {
    id: "research-article",
    format: "typst",
    description: "General research article template with Chinese support",
    engine: "typst",
    requires: [],
    variables: [
      { name: "title", required: true },
      { name: "authors", type: "array", default: [] },
      { name: "abstract", type: "string" },
      { name: "keywords", type: "array", default: [] },
      { name: "bibliography", default: "ref" },
      { name: "paper", default: "a4" },
      { name: "font", default: "Linux Libertine" },
      { name: "cjk_font", default: "Noto Serif CJK SC" },
    ],
    sectioning: { style: "numbered", maxDepth: 3 },
    renderMain(vars, body, options) {
      const title = vars.title || "Untitled";
      const authors = vars.authors || [];
      const abstract = vars.abstract || "";
      const keywords = vars.keywords || [];
      const bibFile = vars.bibliography || "ref";
      const paper = vars.paper || "a4";
      const font = vars.font || "Linux Libertine";
      const cjkFont = vars.cjk_font || "Noto Serif CJK SC";
      const bodyContent = buildBodyContent(body, options, "typst");

      const authorNames = authors.map((a: any) => `"${escapeTypstString(a.name || "")}"`).join(", ");
      const authorBlock = formatTypstAuthors(authors);
      const abstractBlock = abstract
        ? `#abstract[
  ${abstract}
]`
        : "";
      const keywordsBlock = keywords.length
        ? `#keywords[${keywords.map((k: string) => escapeTypstString(k)).join(", ")}]`
        : "";

      return `#set document(title: "${escapeTypstString(title)}"${authorNames ? `, author: (${authorNames})` : ""})
#set page(paper: "${paper}", margin: (x: 2.5cm, y: 2.5cm))
#set text(font: ("${font}", "${cjkFont}"), size: 11pt)
#set heading(numbering: "1.")
#show heading: set text(weight: "bold")

#align(center)[
  #text(size: 17pt, weight: "bold")[${title}]
  #v(1em)
  ${authorBlock}
  #v(1em)
]

${abstractBlock}
${keywordsBlock}

${bodyContent}

#bibliography("${bibFile}.bib")
`;
    },
  },
};

/**
 * List all built-in template IDs for a given format.
 */
export function listBuiltinTemplates(format: DocExportFormat): DocTemplateConfig[] {
  return Object.values(BUILTIN_TEMPLATES).filter((t) => t.format === format);
}

/**
 * Get a built-in template by ID.
 */
export function getBuiltinTemplate(id: string): BuiltinTemplate | undefined {
  return BUILTIN_TEMPLATES[id];
}

/**
 * Get any template (external or built-in) by ID.
 * When wsRoot is provided, external templates take priority.
 */
export async function getTemplate(
  id: string,
  wsRoot?: string,
  format: DocExportFormat = "latex"
): Promise<BuiltinTemplate | ExternalTemplate | undefined> {
  if (wsRoot) {
    const dir = await resolveTemplateDir(id, format, wsRoot);
    if (dir) {
      const ext = await loadExternalTemplate(dir);
      if (ext) {
        return ext;
      }
    }
  }
  return getBuiltinTemplate(id);
}

/**
 * List all templates (external + built-in) for a format.
 * External templates override built-ins with the same ID.
 */
export async function listTemplates(
  format: DocExportFormat = "latex",
  wsRoot?: string
): Promise<DocTemplateConfig[]> {
  const builtin = listBuiltinTemplates(format);
  if (!wsRoot) {
    return builtin;
  }
  const external = await listExternalTemplates(format, wsRoot);
  const merged = new Map<string, DocTemplateConfig>();
  for (const b of builtin) {
    merged.set(b.id, b);
  }
  for (const e of external) {
    merged.set(e.id, e);
  }
  return Array.from(merged.values());
}

/**
 * Render a template with variables and body content.
 *
 * When wsRoot is provided, external templates are discovered first.
 * If an external template has a main.tex skeleton, it is rendered via the
 * lightweight substitution engine; otherwise the built-in renderMain() is used.
 * Template dependency files are returned so they can be copied to the build dir.
 */
export async function renderTemplate(
  templateId: string,
  vars: Record<string, any>,
  body: string,
  options?: { splitSections?: boolean; sections?: DocSection[] },
  wsRoot?: string,
  format: DocExportFormat = "latex"
): Promise<{
  mainContent: string;
  engine: string;
  templateAssets?: Array<{ srcPath: string; destPath: string }>;
}> {
  const template = await getTemplate(templateId, wsRoot, format);

  if (!template) {
    // Fallback to default template for the format
    const fallback =
      format === "typst"
        ? BUILTIN_TEMPLATES["research-article"]
        : BUILTIN_TEMPLATES.article;
    return {
      mainContent: fallback.renderMain(vars, body, options),
      engine: fallback.engine,
    };
  }

  // External template
  if ("templateDir" in template) {
    const ext = template as ExternalTemplate;
    let mainContent: string;
    if (ext.mainTemplatePath) {
      const rendered = await renderExternalTemplate(
        ext,
        vars,
        body,
        options
      );
      mainContent = rendered.mainContent;
    } else {
      // No skeleton: fall back to built-in renderer if ID matches a built-in
      const builtin = getBuiltinTemplate(templateId);
      if (builtin) {
        mainContent = builtin.renderMain(vars, body, options);
      } else {
        throw new Error(
          `External template "${templateId}" has no skeleton and no built-in fallback`
        );
      }
    }
    const templateAssets = ext.resolvedRequires.map((r) => ({
      srcPath: r.srcPath,
      destPath: r.fileName,
    }));
    return {
      mainContent,
      engine: ext.engine || (format === "typst" ? "typst" : "xelatex"),
      templateAssets,
    };
  }

  // Built-in template
  const builtin = template as BuiltinTemplate;
  return {
    mainContent: builtin.renderMain(vars, body, options),
    engine: builtin.engine,
  };
}

// ============================================================================
// Typst helpers
// ============================================================================

function escapeTypstString(text: string): string {
  return text.replace(/\\/g, "\\\\").replace(/"/g, '\\"');
}

function formatTypstAuthors(authors: any[]): string {
  if (!authors || authors.length === 0) return "";
  return authors
    .map((a) => {
      const name = a.name || "";
      const aff = a.affiliation ? ` — ${a.affiliation}` : "";
      const email = a.email ? ` <${a.email}>` : "";
      return `${name}${aff}${email}`;
    })
    .join(", ");
}
