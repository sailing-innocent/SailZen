import {
  AssembledDocument,
  DocExportConfig,
  DocProfile,
  GeneratedDocument,
  NoteProps,
  NotePropsByIdDict,
  ResolvedAsset,
} from "@saili/common-all";
import path from "path";

/**
 * Generate LaTeX output from an assembled document and profile.
 *
 * This is a minimal viable backend that handles:
 * - Basic markdown → LaTeX conversion
 * - ::cite[keys] → \cite{keys}
 * - ::figure[cap](src) → \begin{figure}...\end{figure}
 * - Headings → \section, \subsection
 * - Code blocks → \begin{verbatim}
 * - Math ($...$, $$...$$) → preserved
 *
 * @param assembled - The assembled markdown document
 * @param profile - The document profile
 * @param exportConfig - The specific export configuration
 * @param notesById - Engine notes (for bib extraction)
 * @param wsRoot - Workspace root path (for resolving image paths)
 * @returns GeneratedDocument with .tex content and .bib content
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

  // Build a map of asset ref → ResolvedAsset for quick lookup
  const assetMap = new Map<string, ResolvedAsset>();
  for (const asset of profile.resolvedAssets || []) {
    assetMap.set(asset.ref, asset);
  }

  // Convert markdown body to LaTeX
  let latexBody = markdownToLatex(body, assetMap);

  // Generate main.tex content using a minimal built-in template
  const title = meta?.title || profile.rootNoteFname;
  const authors = meta?.authors || [];
  const authorLines = authors
    .map(
      (a) =>
        `\\author{${escapeLatex(a.name)}${a.affiliation ? ` \\\\ ${escapeLatex(a.affiliation)}` : ""}}`
    )
    .join("\n");

  const bibStyle = exportConfig.vars?.bibliographystyle || "plain";
  const bibFile = exportConfig.vars?.bibliography || "ref";

  const mainContent = `\\documentclass{article}
\\usepackage[UTF8]{ctex}
\\usepackage{graphicx}
\\usepackage{amsmath}
\\usepackage{amsthm}
\\usepackage{hyperref}
\\usepackage{listings}
\\usepackage{xcolor}

\\title{${escapeLatex(title)}}
${authorLines}

\\begin{document}
\\maketitle

${latexBody}

\\bibliographystyle{${bibStyle}}
\\bibliography{${bibFile}}
\\end{document}
`;

  // Generate bibliography
  const bibContent = generateBibTeX(profile.citations, notesById);

  // Generate latexmkrc for user-driven compilation
  const latexmkrcContent = generateLatexmkrc(exportConfig);

  // Collect asset files to copy into the project-level shared figures/ directory.
  // The destPath is relative to the project output root (parent of format-specific dir).
  const assetFiles: Array<{ srcPath: string; destPath: string }> = [];
  for (const asset of profile.resolvedAssets || []) {
    if (wsRoot && asset.path) {
      // Use path.join to handle Windows backslashes correctly
      const srcPath = asset.path.startsWith("/") || /^[A-Za-z]:/.test(asset.path)
        ? asset.path
        : path.join(wsRoot, asset.path);
      const fileName = path.basename(asset.path);
      // destPath uses forward slashes for cross-platform consistency
      // (LaTeX \includegraphics and other backends expect / separators)
      assetFiles.push({
        srcPath,
        destPath: `figures/${fileName}`,
      });
    }
  }

  return {
    mainContent,
    ext: "tex",
    extraFiles: [
      {
        path: `${bibFile}.bib`,
        content: bibContent,
      },
      {
        path: "latexmkrc",
        content: latexmkrcContent,
      },
    ],
    assetFiles,
    meta: {
      templateUsed: exportConfig.template || "article",
      format: "latex",
      timestamp: Date.now(),
    },
  };
}

/**
 * Convert markdown body to LaTeX content.
 * This is a rule-based converter covering common markdown constructs.
 */
function markdownToLatex(
  md: string,
  assetMap: Map<string, ResolvedAsset>
): string {
  let tex = md;

  // ==========================================================================
  // Phase 1: Protect special blocks so inline syntax won't accidentally
  // match inside them (e.g. back-ticks inside code blocks).
  // ==========================================================================
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
    (_m, caption, src, _opts) => {
      const asset = assetMap.get(src);
      // Project-level shared figures/ directory: reference from latex/main.tex
      // using ../figures/ so that LaTeX, Typst, and Slidev can all share the same images.
      const fileName = asset?.path
        ? asset.path.replace(/\\/g, "/").split("/").pop() || src
        : src;
      const latexPath = `../figures/${fileName}`;
      const figCaption = caption || asset?.caption || "";
      const figLabel = asset?.label || `fig:${src}`;
      const width = asset?.width || "0.8\\textwidth";
      return `\\begin{figure}[htbp]\n  \\centering\n  \\includegraphics[width=${width}]{${latexPath}}\n  \\caption{${escapeLatex(figCaption)}}\n  \\label{${figLabel}}\n\\end{figure}`;
    }
  );

  // 1.5 Protect inline code `code` (AFTER code blocks)
  protect(/`([^`]+)`/g, (_m, code) => {
    // Do NOT escape backslashes here – \texttt can handle them fine,
    // and escaping would turn \section into \\textbackslash{}section.
    return `\\texttt{${escapeLatexInlineCode(code)}}`;
  });

  // ==========================================================================
  // Phase 2: Convert remaining markdown syntax to LaTeX
  // ==========================================================================

  // Headings
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

  // Bold **text**
  tex = tex.replace(/\*\*([^*]+)\*\*/g, (_m, text) => {
    return `\\textbf{${escapeLatex(text)}}`;
  });

  // Italic *text* (but not ** which is already handled)
  tex = tex.replace(/(?<!\*)\*([^*]+)\*(?!\*)/g, (_m, text) => {
    return `\\textit{${escapeLatex(text)}}`;
  });

  // Links [text](url)
  tex = tex.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_m, text, url) => {
    return `\\href{${url}}{${escapeLatex(text)}}`;
  });

  // Wikilinks [[note]] → plain text (or \ref if we had labels)
  tex = tex.replace(/\[\[([^\]]+)\]\]/g, (_m, ref) => {
    return escapeLatex(ref);
  });

  // Note refs ![[note]] → removed (already expanded by assembler)
  // But in case there are leftovers:
  tex = tex.replace(/!?\[\[([^\]]+)\]\]/g, "");

  // Horizontal rules
  tex = tex.replace(/^---+\s*$/gm, "\\hrulefill\n");

  // Blockquotes > text
  tex = tex.replace(/^\u003e\s+(.+)$/gm, (_m, text) => {
    return `\\begin{quote}\n${escapeLatex(text)}\n\\end{quote}`;
  });

  // Unordered lists (- item)
  // We process list items and close itemize environments properly.
  tex = processLists(tex);

  // ==========================================================================
  // Phase 3: Escape remaining plain text, but protect already-generated
  // LaTeX commands so escapeLatex won't touch them.
  // ==========================================================================

  // Protect all LaTeX commands we just generated so escapeLatex won't touch them
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

/**
 * Process unordered markdown lists and emit proper LaTeX itemize environments.
 */
function processLists(tex: string): string {
  const lines = tex.split("\n");
  const out: string[] = [];
  let inList = false;
  let lastListLine = -1;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const listMatch = line.match(/^([ \t]*)-\s+(.+)$/);

    if (listMatch) {
      const indent = listMatch[1].length;
      const text = listMatch[2];

      if (!inList) {
        out.push("\\begin{itemize}");
        inList = true;
      }
      // TODO: handle nested lists by tracking indent depth
      out.push(`  \\item ${text}`);
      lastListLine = out.length - 1;
    } else {
      // Check if this is a continuation of a list item (indented line
      // immediately following a list item).
      if (inList && line.trim() !== "" && line.match(/^[ \t]+/)) {
        // Append to previous list item
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

/**
 * Generate BibTeX content from citation keys and notes.
 */
function generateBibTeX(
  citations: string[],
  notesById: NotePropsByIdDict
): string {
  const entries: string[] = [];

  for (const key of citations) {
    // Try to find a bib note for this key
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
      // Fallback: create a placeholder entry
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

/**
 * Generate a latexmkrc file for user-driven PDF compilation.
 *
 * The plugin focuses on text processing; compilation is left to the user
 * who can run `latexmk` in the output directory.
 */
function generateLatexmkrc(exportConfig: DocExportConfig): string {
  const engine = exportConfig.vars?.latexEngine || "xelatex";
  const bibEngine = exportConfig.vars?.bibEngine || "bibtex";

  return `# SailZen Auto-Generated latexmkrc
# Run: latexmk main.tex
# Or:  latexmk -pdf main.tex

# LaTeX engine
$pdf_mode = 5;  # 5 = xelatex, 4 = lualatex, 1 = pdflatex
$pdflatex = "${engine} %O %S";
$xelatex = "${engine} -shell-escape %O %S";
$lualatex = "${engine} %O %S";

# Bibliography engine
$bibtex = "${bibEngine} %O %S";
$bibtex_use = 2;  # run bibtex/biber when needed

# Clean up auxiliary files on cleanup
$clean_ext = "aux bbl blg log out toc fls fdb_latexmk synctex.gz";

# Preview settings (optional)
$preview_mode = 0;
$pdf_previewer = "start";
`;
}

/**
 * Escape special LaTeX characters in plain text.
 * Does NOT escape backslashes – those are assumed to be LaTeX commands
 * that have already been protected.
 */
function escapeLatex(text: string): string {
  return (
    text
      // Backslash is intentionally NOT escaped here – all legitimate
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

/**
 * Escape special LaTeX characters inside \texttt{...}.
 *
 * Unlike plain text, inline code is meant to display LaTeX source verbatim.
 * Therefore backslashes ARE escaped (\ → \textbackslash{}) so that
 * `\section{Foo}` renders as literal text rather than executing the command.
 */
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
