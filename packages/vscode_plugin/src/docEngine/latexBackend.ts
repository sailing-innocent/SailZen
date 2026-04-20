/**
 * @file latexBackend.ts
 * @brief LaTeX code generation backend for SailZen Doc Engine
 * @description Converts assembled markdown to LaTeX using built-in templates.
 *   Supports ::cite, ::figure, ::table, math environments, algorithms,
 *   conditionals, markdown tables, lists, footnotes, and section splitting.
 */

import {
  AssembledDocument,
  DocExportConfig,
  DocProfile,
  DocSection,
  GeneratedDocument,
  NoteProps,
  NotePropsByIdDict,
  ResolvedAsset,
} from "@saili/common-all";
import path from "path";
import { renderTemplate, resolveTemplateVars } from "./templateEngine";

// ============================================================================
// Public API
// ============================================================================

/**
 * Generate LaTeX output from an assembled document and profile.
 *
 * Enhanced capabilities over MVP:
 * - Template-driven preamble/documentclass selection
 * - ::table directives with markdown table wrapping
 * - ::theorem / ::proof / ::definition / ::lemma / ::corollary / ::proposition / ::remark
 * - ::algorithm with ::input and ::output
 * - ::if-format[latex] conditional blocks
 * - Markdown tables → tabular
 * - Ordered lists → enumerate
 * - Footnotes
 * - Optional section splitting into separate .tex files
 */
export function generateLatex(
  assembled: AssembledDocument,
  profile: DocProfile,
  exportConfig: DocExportConfig,
  notesById: NotePropsByIdDict,
  wsRoot?: string
): GeneratedDocument {
  const { body } = assembled;
  const { meta } = profile;

  // Build asset map for figure resolution
  const assetMap = new Map<string, ResolvedAsset>();
  for (const asset of profile.resolvedAssets || []) {
    assetMap.set(asset.ref, asset);
  }

  // Convert markdown body to LaTeX
  let latexBody = markdownToLatex(body, assetMap);

  // Resolve template variables
  const templateVars = resolveTemplateVars(profile, exportConfig);

  // Optional section splitting
  const splitSections = exportConfig.vars?.splitSections === true;
  let sections: DocSection[] | undefined;
  if (splitSections) {
    sections = splitIntoSections(latexBody);
  }

  // Render main.tex via template engine
  const templateId = exportConfig.template || "article";
  const rendered = renderTemplate(templateId, templateVars, latexBody, {
    splitSections,
    sections,
  });

  // Generate bibliography
  const bibFile = exportConfig.vars?.bibliography || "ref";
  const bibContent = generateBibTeX(profile.citations, notesById);

  // Generate latexmkrc for user-driven compilation
  const latexmkrcContent = generateLatexmkrc(exportConfig, rendered.engine);

  // Collect asset files to copy into the project-level shared figures/ directory.
  const assetFiles: Array<{ srcPath: string; destPath: string }> = [];
  for (const asset of profile.resolvedAssets || []) {
    if (wsRoot && asset.path) {
      const srcPath =
        asset.path.startsWith("/") || /^[A-Za-z]:/.test(asset.path)
          ? asset.path
          : path.join(wsRoot, asset.path);
      const fileName = path.basename(asset.path);
      assetFiles.push({
        srcPath,
        destPath: `figures/${fileName}`,
      });
    }
  }

  const extraFiles: Array<{ path: string; content: string }> = [
    { path: `${bibFile}.bib`, content: bibContent },
    { path: "latexmkrc", content: latexmkrcContent },
  ];

  return {
    mainContent: rendered.mainContent,
    ext: "tex",
    extraFiles,
    assetFiles,
    sections,
    meta: {
      templateUsed: templateId,
      format: "latex",
      timestamp: Date.now(),
      engine: rendered.engine,
    },
  };
}

// ============================================================================
// Markdown → LaTeX Converter
// ============================================================================

function markdownToLatex(
  md: string,
  assetMap: Map<string, ResolvedAsset>
): string {
  let tex = md;

  // ========================================================================
  // Phase 1: Protect special blocks so inline syntax won't accidentally
  // match inside them.
  // ========================================================================
  const protectedBlocks: string[] = [];
  function protect(
    re: RegExp,
    replacer: (m: string, ...args: any[]) => string
  ): void {
    tex = tex.replace(re, (m, ...args) => {
      const placeholder = `\u0000${protectedBlocks.length}\u0000`;
      protectedBlocks.push(replacer(m, ...args));
      return placeholder;
    });
  }

  // 1.1 Protect code blocks FIRST (before inline code)
  protect(/```(?:\w+)?\r?\n([\s\S]*?)```/g, (_m, code) => {
    return `\\begin{verbatim}\n${code.trimEnd()}\n\\end{verbatim}`;
  });

  // 1.2 Protect block math $$...$$
  protect(/\$\$([\s\S]*?)\$\$/g, (_m, math) => {
    return `\\[\n${math.trim()}\n\\]`;
  });

  // 1.2b Protect inline math $...$ (must come after block math)
  protect(/(?<!\$)\$([^$\n]+?)\$(?!\$)/g, (_m, math) => {
    return `$${math.trim()}$`;
  });

  // 1.3 Protect ::cite directives
  protect(/::cite\[([^\]]+)\]/g, (_m, keys) => {
    const cleanKeys = keys
      .split(/,\s*/)
      .map((k: string) => k.trim())
      .filter(Boolean)
      .join(", ");
    return `\\cite{${cleanKeys}}`;
  });

  // 1.4 Protect ::figure directives
  protect(
    /::figure\[([^\]]*)\]\s*\(([^)]+)\)(?:\s*\{([^}]*)\})?/g,
    (_m, caption, src, optsStr) => {
      const asset = assetMap.get(src);
      const fileName = asset?.path
        ? asset.path.replace(/\\/g, "/").split("/").pop() || src
        : src;
      const latexPath = `../figures/${fileName}`;
      const figCaption = caption || asset?.caption || "";
      let figLabel = asset?.label || `fig:${src}`;
      let width = asset?.width || "0.8\\textwidth";
      let placement = "htbp";

      // Parse simple opts: width, placement, label overrides
      if (optsStr) {
        const widthMatch = optsStr.match(/width[=:]\s*"?([^",\s}]+)"?/);
        if (widthMatch) width = widthMatch[1];
        const placementMatch = optsStr.match(/placement[=:]\s*"?([^",\s}]+)"?/);
        if (placementMatch) placement = placementMatch[1];
        const labelMatch = optsStr.match(/label[=:]\s*"?([^",\s}]+)"?/);
        if (labelMatch) figLabel = labelMatch[1];
      }

      return `\\begin{figure}[${placement}]\n  \\centering\n  \\includegraphics[width=${width}]{${latexPath}}\n  \\caption{${escapeLatex(figCaption)}}\n  \\label{${figLabel}}\n\\end{figure}`;
    }
  );

  // 1.4b Protect ::ref directives
  protect(/::ref\[([^\]]+)\]/g, (_m, label) => {
    return `\\ref{${label}}`;
  });

  // 1.5 Protect ::table directives + following markdown table
  protect(
    /::table\[([^\]]*)\]\s*\(([^)]+)\)(?:\s*\{([^}]*)\})?\s*\n((?:\|[^\n]*\|[ \t]*(?:\r?\n|$))+)/g,
    (_m, caption, label, _opts, tableMd) => {
      const tabular = markdownTableToLatex(tableMd);
      return `\\begin{table}[htbp]\n\\centering\n\\caption{${escapeLatex(caption)}}\\label{${label}}\n${tabular}\n\\end{table}`;
    }
  );

  // 1.6 Protect standalone ::table directives (without following table)
  protect(
    /::table\[([^\]]*)\]\s*\(([^)]+)\)(?:\s*\{([^}]*)\})?/g,
    (_m, caption, label, _opts) => {
      return `\\begin{table}[htbp]\n\\centering\n\\caption{${escapeLatex(caption)}}\\label{${label}}\n\\end{table}`;
    }
  );

  // 1.7 Protect math environments ::theorem, ::lemma, ::corollary, ::proposition, ::definition, ::remark
  protect(
    /::(theorem|lemma|corollary|proposition|definition|remark)\[([^\]]*)\](?:\s*\{([^}]*)\})?\s*\n([\s\S]*?)\n::end/g,
    (_m, env, title, opts, content) => {
      const labelMatch = opts?.match(/label:\s*"([^"]*)"/);
      const label = labelMatch ? `\\label{${labelMatch[1]}}` : "";
      const titlePart = title ? `[${escapeLatex(title)}]` : "";
      const inner = convertInlineMarkdownToLatex(content);
      return `\\begin{${env}}${titlePart}${label}\n${inner}\n\\end{${env}}`;
    }
  );

  // 1.8 Protect ::proof
  protect(
    /::proof\s*\n([\s\S]*?)\n::end/g,
    (_m, content) => {
      const inner = convertInlineMarkdownToLatex(content);
      return `\\begin{proof}\n${inner}\n\\end{proof}`;
    }
  );

  // 1.9 Protect ::algorithm with ::input / ::output
  protect(
    /::algorithm\[([^\]]*)\](?:\s*\{([^}]*)\})?\s*\n([\s\S]*?)\n::end/g,
    (_m, title, opts, content) => {
      const labelMatch = opts?.match(/label:\s*"([^"]*)"/);
      const label = labelMatch ? `\\label{${labelMatch[1]}}` : "";
      let inner = content;
      inner = inner.replace(/::input\[([^\]]*)\]/g, (_m2, inp) => `\\Require ${inp}`);
      inner = inner.replace(/::output\[([^\]]*)\]/g, (_m2, out) => `\\Ensure ${out}`);
      // Numbered/bullet steps -> \State
      inner = inner.replace(/^(\d+)\.\s+(.+)$/gm, (_m2, _num, step) => `\\State ${step}`);
      inner = inner.replace(/^-\s+(.+)$/gm, (_m2, step) => `\\State ${step}`);
      // Indented lines as continuation
      inner = inner.replace(/^[ \t]+(.+)$/gm, (_m2, line) => `  ${line}`);
      return `\\begin{algorithm}[htbp]\n\\caption{${escapeLatex(title)}}${label}\n\\begin{algorithmic}\n${inner}\n\\end{algorithmic}\n\\end{algorithm}`;
    }
  );

  // 1.10 Protect ::if-format[latex] (keep content)
  protect(
    /::if-format\[latex\]\s*\n([\s\S]*?)\n::end/g,
    (_m, content) => convertInlineMarkdownToLatex(content)
  );

  // 1.11 Protect ::if-format[other] (strip content for LaTeX backend)
  protect(
    /::if-format\[(?!latex)[^\]]+\]\s*\n([\s\S]*?)\n::end/g,
    () => ""
  );

  // 1.12 Protect inline code `code` (AFTER code blocks)
  protect(/`([^`]+)`/g, (_m, code) => {
    return `\\texttt{${escapeLatexInlineCode(code)}}`;
  });

  // ========================================================================
  // Phase 2: Convert remaining markdown syntax to LaTeX
  // ========================================================================

  // 2.1 Headings
  tex = tex.replace(/^(#{1,6})\s+(.+)$/gm, (_m, hashes, text) => {
    const level = hashes.length;
    const cmd =
      level === 1
        ? "section"
        : level === 2
          ? "subsection"
          : level === 3
            ? "subsubsection"
            : "paragraph";
    return `\\${cmd}{${escapeLatex(text.trim())}}`;
  });

  // 2.2 Bold **text**
  tex = tex.replace(/\*\*([^*]+)\*\*/g, (_m, text) => {
    return `\\textbf{${escapeLatex(text)}}`;
  });

  // 2.3 Italic *text* (but not ** which is already handled)
  tex = tex.replace(/(?<!\*)\*([^*]+)\*(?!\*)/g, (_m, text) => {
    return `\\textit{${escapeLatex(text)}}`;
  });

  // 2.4 Links [text](url)
  tex = tex.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_m, text, url) => {
    return `\\href{${url}}{${escapeLatex(text)}}`;
  });

  // 2.5 Wikilinks [[note]] → plain text (but preserve anchors ^block-id)
  tex = tex.replace(/\[\[([^\]^]+)\^([^\]]+)\]\]/g, (_m, ref, anchor) => {
    return `${escapeLatex(ref)}~(\\ref{${anchor}})`;
  });
  tex = tex.replace(/\[\[([^\]]+)\]\]/g, (_m, ref) => {
    return escapeLatex(ref);
  });

  // 2.6 Note refs ![[note]] → removed (already expanded by assembler)
  tex = tex.replace(/!?\[\[([^\]]+)\]\]/g, "");

  // 2.7 Horizontal rules
  tex = tex.replace(/^---+\s*$/gm, "\\hrulefill\n");

  // 2.8 Blockquotes > text
  tex = tex.replace(/^>\s+(.+)$/gm, (_m, text) => {
    return `\\begin{quote}\n${escapeLatex(text)}\n\\end{quote}`;
  });

  // 2.9 Markdown tables (not already wrapped by ::table)
  tex = convertMarkdownTables(tex);

  // 2.10 Footnotes
  tex = convertFootnotes(tex);

  // 2.11 Unordered lists
  tex = processUnorderedLists(tex);

  // 2.12 Ordered lists
  tex = processOrderedLists(tex);

  // ========================================================================
  // Phase 3: Escape remaining plain text, but protect already-generated
  // LaTeX commands so escapeLatex won't touch them.
  // ========================================================================

  // Protect all LaTeX commands we just generated
  const latexCommands: string[] = [];
  tex = tex.replace(
    /\\[a-zA-Z]+(?:\[[^\]]*\])?(?:\{[^{}]*\})?/g,
    (m) => {
      const placeholder = `\u0001${latexCommands.length}\u0001`;
      latexCommands.push(m);
      return placeholder;
    }
  );

  // Now escape remaining plain text for LaTeX
  tex = escapeLatex(tex);

  // Restore LaTeX commands
  tex = tex.replace(/\u0001(\d+)\u0001/g, (_m, idx) => latexCommands[parseInt(idx, 10)]);

  // Restore protected blocks
  tex = tex.replace(/\u0000(\d+)\u0000/g, (_m, idx) => protectedBlocks[parseInt(idx, 10)]);

  // Multiple consecutive newlines → single paragraph break
  tex = tex.replace(/\n{3,}/g, "\n\n");

  return tex;
}

// ============================================================================
// Inline markdown converter (for use inside protected blocks)
// ============================================================================

function convertInlineMarkdownToLatex(md: string): string {
  let tex = md;

  // Protect inline math first so escapeLatex won't touch it
  const protectedMath: string[] = [];
  tex = tex.replace(/\$([^$\n]+?)\$/g, (m) => {
    const placeholder = `\u0002${protectedMath.length}\u0002`;
    protectedMath.push(m);
    return placeholder;
  });
  // Protect block math
  tex = tex.replace(/\$\$([\s\S]*?)\$\$/g, (_m, math) => {
    const placeholder = `\u0002${protectedMath.length}\u0002`;
    protectedMath.push(`\\[\n${math.trim()}\n\\]`);
    return placeholder;
  });

  // Bold
  tex = tex.replace(/\*\*([^*]+)\*\*/g, (_m, text) => `\\textbf{${escapeLatex(text)}}`);
  // Italic
  tex = tex.replace(/(?<!\*)\*([^*]+)\*(?!\*)/g, (_m, text) => `\\textit{${escapeLatex(text)}}`);
  // Inline code
  tex = tex.replace(/`([^`]+)`/g, (_m, code) => `\\texttt{${escapeLatexInlineCode(code)}}`);
  // Links
  tex = tex.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_m, text, url) => `\\href{${url}}{${escapeLatex(text)}}`);
  // Escape remaining plain text
  tex = escapeLatex(tex);

  // Restore math
  tex = tex.replace(/\u0002(\d+)\u0002/g, (_m, idx) => protectedMath[parseInt(idx, 10)]);
  return tex;
}

// ============================================================================
// Markdown table → tabular
// ============================================================================

function markdownTableToLatex(tableMd: string): string {
  const lines = tableMd.trim().split("\n").filter((l) => l.trim());
  if (lines.length < 2) return "";

  const headerCells = lines[0]
    .split("|")
    .map((c) => c.trim())
    .filter((c) => c !== "");
  const sepCells = lines[1]
    .split("|")
    .map((c) => c.trim())
    .filter((c) => c !== "");

  const aligns = sepCells.map((c) => {
    if (c.startsWith(":") && c.endsWith(":")) return "c";
    if (c.endsWith(":")) return "r";
    return "l";
  });
  const colSpec = aligns.join("");

  let latex = `\\begin{tabular}{${colSpec}}\n\\hline\n`;
  latex += headerCells.map((c) => escapeLatex(c)).join(" & ") + " \\\\\n\\hline\n";

  for (let i = 2; i < lines.length; i++) {
    const cells = lines[i]
      .split("|")
      .map((c) => c.trim())
      .filter((c) => c !== "");
    if (cells.length === 0) continue;
    latex += cells.map((c) => escapeLatex(c)).join(" & ") + " \\\\\n";
  }
  latex += "\\hline\n\\end{tabular}";
  return latex;
}

function convertMarkdownTables(tex: string): string {
  // Match standalone markdown tables (not already protected by ::table)
  // Table must start at beginning of line
  const tableRegex = /^(\|[^\n]*\|[ \t]*\r?\n)(\|[-:\| \t]*\|[ \t]*\r?\n)((?:\|[^\n]*\|[ \t]*(?:\r?\n|$))+)/gm;
  return tex.replace(tableRegex, (_m, headerLine, sepLine, bodyLines) => {
    const tableMd = (headerLine + sepLine + bodyLines).trimEnd();
    return `\n${markdownTableToLatex(tableMd)}\n`;
  });
}

// ============================================================================
// Footnotes
// ============================================================================

function convertFootnotes(tex: string): string {
  const lines = tex.split("\n");
  const outLines: string[] = [];
  const footnotes: Record<string, string> = [];
  let i = 0;

  while (i < lines.length) {
    const defMatch = lines[i].match(/^\[\^(\d+)\]:\s+(.*)$/);
    if (defMatch) {
      let content = defMatch[2];
      i++;
      while (
        i < lines.length &&
        lines[i].trim() !== "" &&
        (lines[i].startsWith(" ") || lines[i].startsWith("\t"))
      ) {
        content += " " + lines[i].trim();
        i++;
      }
      footnotes[`^${defMatch[1]}`] = content;
    } else {
      outLines.push(lines[i]);
      i++;
    }
  }

  let result = outLines.join("\n");
  result = result.replace(/\[\^(\d+)\]/g, (_m, num) => {
    const content = footnotes[`^${num}`];
    return content ? `\\footnote{${escapeLatex(content)}}` : `\\footnote{${num}}`;
  });

  return result;
}

// ============================================================================
// Lists
// ============================================================================

function processUnorderedLists(tex: string): string {
  const lines = tex.split("\n");
  const out: string[] = [];
  let inList = false;
  let lastListLine = -1;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const listMatch = line.match(/^([ \t]*)-\s+(.+)$/);

    if (listMatch) {
      if (!inList) {
        out.push("\\begin{itemize}");
        inList = true;
      }
      out.push(`  \\item ${listMatch[2]}`);
      lastListLine = out.length - 1;
    } else {
      if (inList && line.trim() !== "" && line.match(/^[ \t]+/)) {
        if (lastListLine >= 0) {
          out[lastListLine] += " " + line.trim();
        }
      } else {
        if (inList) {
          out.push("\\end{itemize}");
          inList = false;
        }
        out.push(line);
      }
    }
  }

  if (inList) {
    out.push("\\end{itemize}");
  }

  return out.join("\n");
}

function processOrderedLists(tex: string): string {
  const lines = tex.split("\n");
  const out: string[] = [];
  let inList = false;
  let lastListLine = -1;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const listMatch = line.match(/^([ \t]*)\d+\.\s+(.+)$/);

    if (listMatch) {
      if (!inList) {
        out.push("\\begin{enumerate}");
        inList = true;
      }
      out.push(`  \\item ${listMatch[2]}`);
      lastListLine = out.length - 1;
    } else {
      if (inList && line.trim() !== "" && line.match(/^[ \t]+/)) {
        if (lastListLine >= 0) {
          out[lastListLine] += " " + line.trim();
        }
      } else {
        if (inList) {
          out.push("\\end{enumerate}");
          inList = false;
        }
        out.push(line);
      }
    }
  }

  if (inList) {
    out.push("\\end{enumerate}");
  }

  return out.join("\n");
}

// ============================================================================
// Section splitting
// ============================================================================

function splitIntoSections(latexBody: string): DocSection[] {
  const lines = latexBody.split("\n");
  const sections: DocSection[] = [];
  let currentSection: DocSection | null = null;
  let currentContent: string[] = [];
  const preambleLines: string[] = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const match = line.match(
      /^(\\(chapter|section|subsection|subsubsection))\{([^}]+)\}/
    );

    if (match) {
      if (currentSection) {
        currentSection.content = currentContent.join("\n").trim();
        sections.push(currentSection);
      } else if (preambleLines.length > 0 && sections.length > 0) {
        // Attach orphaned preamble to first section
        sections[0].content =
          preambleLines.join("\n") + "\n\n" + sections[0].content;
      }

      const level =
        match[2] === "chapter"
          ? 1
          : match[2] === "section"
            ? 2
            : match[2] === "subsection"
              ? 3
              : 4;

      const safeName = match[3]
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "_")
        .replace(/^_+|_+$/g, "");

      currentSection = {
        title: match[3],
        level,
        content: line,
        fileName: `${String(sections.length).padStart(2, "0")}_${safeName}.tex`,
      };
      currentContent = [line];
    } else if (currentSection) {
      currentContent.push(line);
    } else {
      preambleLines.push(line);
    }
  }

  if (currentSection) {
    currentSection.content = currentContent.join("\n").trim();
    sections.push(currentSection);
  }

  // Attach leading preamble to first section if any
  if (preambleLines.length > 0 && sections.length > 0) {
    const preamble = preambleLines.join("\n").trim();
    if (preamble) {
      sections[0].content = preamble + "\n\n" + sections[0].content;
    }
  }

  return sections;
}

// ============================================================================
// BibTeX Generation
// ============================================================================

function generateBibTeX(
  citations: string[],
  notesById: NotePropsByIdDict
): string {
  const entries: string[] = [];

  for (const key of citations) {
    let found = false;
    for (const note of Object.values(notesById)) {
      const docFm = note.custom?.doc;
      if (docFm?.bibtex?.key === key) {
        entries.push(bibEntryToString(docFm.bibtex));
        found = true;
        break;
      }
    }
    if (!found) {
      entries.push(
        `@misc{${key},\n  title = {${key}},\n  note = {Citation source not found in notes}\n}`
      );
    }
  }

  return entries.join("\n\n");
}

function bibEntryToString(entry: {
  type: string;
  key: string;
  fields: Record<string, string>;
}): string {
  const fieldLines = Object.entries(entry.fields).map(
    ([k, v]) => `  ${k} = {${v}}`
  );
  return `@${entry.type}{${entry.key},\n${fieldLines.join(",\n")}\n}`;
}

// ============================================================================
// latexmkrc Generation
// ============================================================================

function generateLatexmkrc(
  exportConfig: DocExportConfig,
  engine?: string
): string {
  const latexEngine = engine || exportConfig.vars?.latexEngine || "xelatex";
  const bibEngine = exportConfig.vars?.bibEngine || "bibtex";

  // Map engine name to latexmk $pdf_mode
  let pdfMode = 5; // default xelatex
  if (latexEngine === "pdflatex") pdfMode = 1;
  else if (latexEngine === "lualatex") pdfMode = 4;

  return `# SailZen Auto-Generated latexmkrc
# Run: latexmk main.tex
# Or:  latexmk -pdf main.tex

# LaTeX engine
$pdf_mode = ${pdfMode};
$pdflatex = "${latexEngine} %O %S";
$xelatex = "${latexEngine} -shell-escape %O %S";
$lualatex = "${latexEngine} %O %S";

# Bibliography engine
$bibtex = "${bibEngine} %O %S";
$bibtex_use = 2;

# Clean up auxiliary files on cleanup
$clean_ext = "aux bbl blg log out toc fls fdb_latexmk synctex.gz";

# Preview settings (optional)
$preview_mode = 0;
$pdf_previewer = "start";
`;
}

// ============================================================================
// LaTeX Escaping
// ============================================================================

function escapeLatex(text: string): string {
  return (
    text
      // Intentionally NOT escaping backslash here – all legitimate
      // LaTeX commands are protected before this function runs.
      .replace(/\{/g, "\\{")
      .replace(/\}/g, "\\}")
      .replace(/\$/g, "\\$")
      .replace(/&/g, "\\&")
      .replace(/#/g, "\\#")
      .replace(/\^/g, "\\^{}")
      .replace(/_/g, "\\_")
      .replace(/%/g, "\\%")
      .replace(/~/g, "\\textasciitilde{}")
      .replace(/"/g, "''")
  );
}

function escapeLatexInlineCode(text: string): string {
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
