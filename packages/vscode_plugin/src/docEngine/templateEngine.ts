/**
 * @file templateEngine.ts
 * @brief Built-in LaTeX template library and variable injection engine
 * @description Provides a collection of academic paper templates (article, acmart,
 *   cvpr, iccv, icml, njuthesis, arxiv) with handlebars-style variable substitution.
 */

import {
  DocExportConfig,
  DocProfile,
  DocSection,
  DocTemplateConfig,
} from "@saili/common-all";

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
      const aff = a.affiliation ? ` \\ ${escapeLatex(a.affiliation)}` : "";
      const email = a.email ? ` \\ \texttt{${escapeLatex(a.email)}}` : "";
      return `\\author{${name}${aff}${email}}`;
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
  engine: "pdflatex" | "xelatex" | "lualatex";
  packages: string[];
  renderMain: (
    vars: Record<string, any>,
    body: string,
    options?: { splitSections?: boolean; sections?: DocSection[] }
  ) => string;
};

const COMMON_PACKAGES = [
  "graphicx",
  "amsmath",
  "amssymb",
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
  options?: { splitSections?: boolean; sections?: DocSection[] }
): string {
  if (options?.splitSections && options?.sections && options.sections.length > 0) {
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
      const bodyContent = buildBodyContent(body, options);

      return `\\documentclass${docOpts}{${docClass}}
\\usepackage[UTF8]{ctex}
${buildPreamble(this.packages)}

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

  "acmart-sigconf": {
    id: "acmart-sigconf",
    format: "latex",
    description: "ACM Conference Paper (sigconf)",
    engine: "xelatex",
    requires: ["acmart.cls"],
    packages: [...COMMON_PACKAGES],
    variables: [
      { name: "title", required: true },
      { name: "authors", type: "array", default: [] },
      { name: "abstract", type: "string" },
      { name: "keywords", type: "array", default: [] },
      { name: "ccs_concepts", type: "array", default: [] },
      { name: "bibliography", default: "ref" },
      { name: "bibliographystyle", default: "ACM-Reference-Format" },
      { name: "documentclass_options", default: "sigconf,authordraft" },
      { name: "copyright", default: "none" },
    ],
    sectioning: { style: "numbered", maxDepth: 3 },
    renderMain(vars, body, options) {
      const docOpts = vars.documentclass_options || "sigconf,authordraft";
      const authors = formatAuthors(vars.authors);
      const abstract = vars.abstract
        ? `\\begin{abstract}\n${vars.abstract}\n\\end{abstract}`
        : "";
      const keywords = formatKeywords(vars.keywords);
      const ccs = (vars.ccs_concepts || []).length
        ? `\\begin{CCSXML}\n${vars.ccs_concepts.join("\n")}\n\\end{CCSXML}\n\\ccsdesc[500]{${vars.ccs_concepts[0]}}`
        : "";
      const bibStyle = vars.bibliographystyle || "ACM-Reference-Format";
      const bibFile = vars.bibliography || "ref";
      const copyright = vars.copyright !== "none" ? vars.copyright : "";
      const bodyContent = buildBodyContent(body, options);

      return `\\documentclass[${docOpts}]{acmart}
${buildPreamble(this.packages)}

\\title{${escapeLatex(vars.title || "Untitled")}}
${authors}
${copyright}

\\begin{document}
\\maketitle
${abstract}
${ccs}
${keywords}

${bodyContent}

\\bibliographystyle{${bibStyle}}
\\bibliography{${bibFile}}
\\end{document}
`;
    },
  },

  cvpr: {
    id: "cvpr",
    format: "latex",
    description: "CVPR Conference Paper",
    engine: "xelatex",
    requires: ["cvpr.sty"],
    packages: [...COMMON_PACKAGES, "cvpr", "times", "epsfig", "graphicx", "amsmath", "amssymb"],
    variables: [
      { name: "title", required: true },
      { name: "authors", type: "array", default: [] },
      { name: "abstract", type: "string" },
      { name: "keywords", type: "array", default: [] },
      { name: "bibliography", default: "ref" },
      { name: "bibliographystyle", default: "ieee_fullname" },
      { name: "cvpr_year", default: new Date().getFullYear() },
    ],
    sectioning: { style: "numbered", maxDepth: 3 },
    renderMain(vars, body, options) {
      const cvprYear = vars.cvpr_year || new Date().getFullYear();
      // CVPR uses a specific author block format
      const authors = (vars.authors || [])
        .map((a: any, idx: number, arr: any[]) => {
          const sep = idx < arr.length - 1 ? "\\and" : "";
          return `\\author{${escapeLatex(a.name)}${sep}}`;
        })
        .join("\n");
      const abstract = vars.abstract
        ? `\\begin{abstract}\n${vars.abstract}\n\\end{abstract}`
        : "";
      const bodyContent = buildBodyContent(body, options);

      return `\\documentclass[10pt,twocolumn,letterpaper]{article}
\\usepackage[cvpr]{ieee_fullname}
\\usepackage{cvpr}
\\usepackage{times}
\\usepackage{epsfig}
\\usepackage{graphicx}
\\usepackage{amsmath}
\\usepackage{amssymb}
${buildPreamble(this.packages.filter((p) => !["cvpr", "times", "epsfig", "graphicx", "amsmath", "amssymb"].includes(p)))}

\\cvprfinalcopy
\\def\\cvprPaperID{****}
\\def\\confName{CVPR}
\\def\\confYear{${cvprYear}}

\\title{${escapeLatex(vars.title || "Untitled")}}
${authors}

\\begin{document}
\\maketitle
${abstract}

${bodyContent}

\\bibliographystyle{ieee_fullname}
\\bibliography{${vars.bibliography || "ref"}}
\\end{document}
`;
    },
  },

  iccv: {
    id: "iccv",
    format: "latex",
    description: "ICCV Conference Paper",
    engine: "xelatex",
    requires: ["iccv.sty"],
    packages: [...COMMON_PACKAGES, "iccv", "times", "epsfig", "graphicx", "amsmath", "amssymb"],
    variables: [
      { name: "title", required: true },
      { name: "authors", type: "array", default: [] },
      { name: "abstract", type: "string" },
      { name: "bibliography", default: "ref" },
      { name: "bibliographystyle", default: "ieee_fullname" },
      { name: "iccv_year", default: new Date().getFullYear() },
    ],
    sectioning: { style: "numbered", maxDepth: 3 },
    renderMain(vars, body, options) {
      const iccvYear = vars.iccv_year || new Date().getFullYear();
      const authors = formatAuthors(vars.authors);
      const abstract = vars.abstract
        ? `\\begin{abstract}\n${vars.abstract}\n\\end{abstract}`
        : "";
      const bodyContent = buildBodyContent(body, options);

      return `\\documentclass[10pt,twocolumn,letterpaper]{article}
\\usepackage[iccv]{ieee_fullname}
\\usepackage{iccv}
\\usepackage{times}
\\usepackage{epsfig}
\\usepackage{graphicx}
\\usepackage{amsmath}
\\usepackage{amssymb}
${buildPreamble(this.packages.filter((p) => !["iccv", "times", "epsfig", "graphicx", "amsmath", "amssymb"].includes(p)))}

\\iccvfinalcopy
\\def\\iccvPaperID{****}
\\def\\confName{ICCV}
\\def\\confYear{${iccvYear}}

\\title{${escapeLatex(vars.title || "Untitled")}}
${authors}

\\begin{document}
\\maketitle
${abstract}

${bodyContent}

\\bibliographystyle{ieee_fullname}
\\bibliography{${vars.bibliography || "ref"}}
\\end{document}
`;
    },
  },

  icml: {
    id: "icml",
    format: "latex",
    description: "ICML Conference Paper",
    engine: "xelatex",
    requires: ["icml2024.sty"],
    packages: [...COMMON_PACKAGES, "icml2024", "times"],
    variables: [
      { name: "title", required: true },
      { name: "authors", type: "array", default: [] },
      { name: "abstract", type: "string" },
      { name: "keywords", type: "array", default: [] },
      { name: "bibliography", default: "ref" },
      { name: "bibliographystyle", default: "icml2024" },
    ],
    sectioning: { style: "numbered", maxDepth: 3 },
    renderMain(vars, body, options) {
      const authors = (vars.authors || [])
        .map((a: any) => {
          const aff = a.affiliation ? `\\icmlaffiliation{${escapeLatex(a.affiliation)}}` : "";
          return `\\icmlauthor{${escapeLatex(a.name)}}{${aff}}`;
        })
        .join("\n");
      const abstract = vars.abstract
        ? `\\begin{abstract}\n${vars.abstract}\n\\end{abstract}`
        : "";
      const keywords = formatKeywords(vars.keywords);
      const bodyContent = buildBodyContent(body, options);

      return `\\documentclass{article}
\\usepackage[accepted]{icml2024}
\\usepackage{times}
${buildPreamble(this.packages.filter((p) => !["icml2024", "times"].includes(p)))}

\\icmltitlerunning{${escapeLatex(vars.title || "Untitled")}}

\\begin{document}
\\twocolumn[
\\icmltitle{${escapeLatex(vars.title || "Untitled")}}
${authors}
${abstract}
${keywords}
]

${bodyContent}

\\bibliography{${vars.bibliography || "ref"}}
\\bibliographystyle{${vars.bibliographystyle || "icml2024"}}
\\end{document}
`;
    },
  },

  njuthesis: {
    id: "njuthesis",
    format: "latex",
    description: "Nanjing University Thesis",
    engine: "xelatex",
    requires: ["njuthesis.cls"],
    packages: [...COMMON_PACKAGES, "njuthesis"],
    variables: [
      { name: "title", required: true },
      { name: "authors", type: "array", default: [] },
      { name: "abstract", type: "string" },
      { name: "abstract_cn", type: "string" },
      { name: "keywords", type: "array", default: [] },
      { name: "keywords_cn", type: "array", default: [] },
      { name: "degree", default: "master" },
      { name: "major", default: "" },
      { name: "supervisor", default: "" },
      { name: "bibliography", default: "ref" },
      { name: "bibliographystyle", default: "gbt7714-numerical" },
    ],
    sectioning: { style: "chapter", maxDepth: 4 },
    renderMain(vars, body, options) {
      const degree = vars.degree || "master";
      const author = vars.authors?.[0];
      const authorName = author ? escapeLatex(author.name) : "Author";
      const supervisor = vars.supervisor ? escapeLatex(vars.supervisor) : "";
      const major = vars.major ? escapeLatex(vars.major) : "";
      const abstractCn = vars.abstract_cn
        ? `\\begin{abstract}[\zhname{摘要}]\n${vars.abstract_cn}\n\\keywords{${(vars.keywords_cn || []).join("；")}}\n\\end{abstract}`
        : "";
      const abstractEn = vars.abstract
        ? `\\begin{abstract}\n${vars.abstract}\n\\keywords{${(vars.keywords || []).join("; ")}}\n\\end{abstract}`
        : "";
      const bodyContent = buildBodyContent(body, options);

      return `\\documentclass[degree=${degree}]{njuthesis}
${buildPreamble(this.packages.filter((p) => p !== "njuthesis"))}

\\title{${escapeLatex(vars.title || "Untitled")}}
\\author{${authorName}}
\\major{${major}}
\\supervisor{${supervisor}}

\\begin{document}
\\maketitle
${abstractCn}
${abstractEn}

${bodyContent}

\\bibliography{${vars.bibliography || "ref"}}
\\bibliographystyle{${vars.bibliographystyle || "gbt7714-numerical"}}
\\end{document}
`;
    },
  },

  arxiv: {
    id: "arxiv",
    format: "latex",
    description: "arXiv Generic Template",
    engine: "xelatex",
    requires: [],
    packages: [...COMMON_PACKAGES, "hyperref", "url"],
    variables: [
      { name: "title", required: true },
      { name: "authors", type: "array", default: [] },
      { name: "abstract", type: "string" },
      { name: "keywords", type: "array", default: [] },
      { name: "bibliography", default: "ref" },
      { name: "bibliographystyle", default: "plainnat" },
      { name: "arxiv_id", default: "" },
    ],
    sectioning: { style: "numbered", maxDepth: 3 },
    renderMain(vars, body, options) {
      const authors = (vars.authors || [])
        .map((a: any) => {
          const aff = a.affiliation ? `\\thanks{${escapeLatex(a.affiliation)}}` : "";
          return `\\author{${escapeLatex(a.name)}${aff}}`;
        })
        .join("\n");
      const abstract = vars.abstract
        ? `\\begin{abstract}\n${vars.abstract}\n\\end{abstract}`
        : "";
      const keywords = formatKeywords(vars.keywords);
      const arxivId = vars.arxiv_id ? `\\arxivid{${vars.arxiv_id}}` : "";
      const bodyContent = buildBodyContent(body, options);

      return `\\documentclass{article}
${buildPreamble(this.packages)}

\\title{${escapeLatex(vars.title || "Untitled")}}
${authors}
${arxivId}

\\begin{document}
\\maketitle
${abstract}
${keywords}

${bodyContent}

\\bibliographystyle{${vars.bibliographystyle || "plainnat"}}
\\bibliography{${vars.bibliography || "ref"}}
\\end{document}
`;
    },
  },
};

/**
 * List all built-in template IDs for a given format.
 */
export function listBuiltinTemplates(format: "latex"): DocTemplateConfig[] {
  return Object.values(BUILTIN_TEMPLATES).filter((t) => t.format === format);
}

/**
 * Get a built-in template by ID.
 */
export function getBuiltinTemplate(id: string): BuiltinTemplate | undefined {
  return BUILTIN_TEMPLATES[id];
}

/**
 * Render a template with variables and body content.
 */
export function renderTemplate(
  templateId: string,
  vars: Record<string, any>,
  latexBody: string,
  options?: { splitSections?: boolean; sections?: DocSection[] }
): { mainContent: string; engine: string } {
  const template = getBuiltinTemplate(templateId);
  if (!template) {
    // Fallback to article
    const fallback = BUILTIN_TEMPLATES.article;
    return {
      mainContent: fallback.renderMain(vars, latexBody, options),
      engine: fallback.engine,
    };
  }
  return {
    mainContent: template.renderMain(vars, latexBody, options),
    engine: template.engine,
  };
}
