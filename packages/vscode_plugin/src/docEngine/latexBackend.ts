import {
  AssembledDocument,
  DocExportConfig,
  DocProfile,
  GeneratedDocument,
  NoteProps,
  NotePropsByIdDict,
} from "@saili/common-all";

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
 * @returns GeneratedDocument with .tex content and .bib content
 */
export function generateLatex(
  assembled: AssembledDocument,
  profile: DocProfile,
  exportConfig: DocExportConfig,
  notesById: NotePropsByIdDict
): GeneratedDocument {
  const { body } = assembled;
  const { meta } = profile;

  // Convert markdown body to LaTeX
  let latexBody = markdownToLatex(body);

  // Generate main.tex content using a minimal built-in template
  const title = meta?.title || profile.rootNoteFname;
  const authors = meta?.authors || [];
  const authorLines = authors
    .map((a) => `\\author{${escapeLatex(a.name)}${a.affiliation ? ` \\\\ ${escapeLatex(a.affiliation)}` : ""}}`)
    .join("\n");

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

\\bibliographystyle{plain}
\\bibliography{ref}
\\end{document}
`;

  // Generate bibliography
  const bibContent = generateBibTeX(profile.citations, notesById);

  return {
    mainContent,
    ext: "tex",
    extraFiles: [
      {
        path: "ref.bib",
        content: bibContent,
      },
    ],
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
function markdownToLatex(md: string): string {
  let tex = md;

  // ::cite[keys] → \cite{keys}
  tex = tex.replace(/::cite\[([^\]]+)\]/g, (_m, keys) => {
    const cleanKeys = keys
      .split(/,\s*/)
      .map((k: string) => k.trim())
      .filter(Boolean)
      .join(", ");
    return `\cite{${cleanKeys}}`;
  });

  // ::figure[caption](src){opts} → figure environment
  tex = tex.replace(
    /::figure\[([^\]]*)\]\s*\(([^)]+)\)(?:\s*\{([^}]*)\})?/g,
    (_m, caption, src, _opts) => {
      return `\begin{figure}[htbp]
  \\centering
  \\includegraphics[width=0.8\\textwidth]{${src}}
  \\caption{${escapeLatex(caption)}}
  \\label{fig:${src}}
\\end{figure}`;
    }
  );

  // Block math $$...$$ → \[ ... \]
  tex = tex.replace(/\$\$([\s\S]*?)\$\$/g, (_m, math) => {
    return `\[\n${math.trim()}\n\]`;
  });

  // Inline math $...$ → preserved (but escape $ in other contexts)
  // This is tricky; we assume $...$ is math and preserve it

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
    return `\\\\${cmd}{${escapeLatex(text.trim())}}`;
  });

  // Bold **text**
  tex = tex.replace(/\*\*([^*]+)\*\*/g, (_m, text) => {
    return `\textbf{${escapeLatex(text)}}`;
  });

  // Italic *text* (but not ** which is already handled)
  tex = tex.replace(/(?<!\*)\*([^*]+)\*(?!\*)/g, (_m, text) => {
    return `\textit{${escapeLatex(text)}}`;
  });

  // Code blocks ```lang\ncode\n```
  tex = tex.replace(
    /```(?:\w+)?\n([\s\S]*?)```/g,
    (_m, code) => {
      return `\begin{verbatim}\n${code.trim()}\n\end{verbatim}`;
    }
  );

  // Inline code `code`
  tex = tex.replace(/`([^`]+)`/g, (_m, code) => {
    return `\texttt{${escapeLatex(code)}}`;
  });

  // Links [text](url)
  tex = tex.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_m, text, url) => {
    return `\href{${url}}{${escapeLatex(text)}}`;
  });

  // Unordered lists (- item)
  tex = tex.replace(/^([ \t]*)-\s+(.+)$/gm, (_m, indent, text) => {
    const depth = indent.length / 2;
    if (depth === 0) {
      return `\begin{itemize}\n  \\item ${escapeLatex(text)}`;
    }
    return `  \\item ${escapeLatex(text)}`;
  });
  // Close itemize (naive: add \end{itemize} before blank lines or end)
  // This is tricky without full parsing; we'll do a simple approximation

  // Wikilinks [[note]] → plain text (or \ref if we had labels)
  tex = tex.replace(/\[\[([^\]]+)\]\]/g, (_m, ref) => {
    return escapeLatex(ref);
  });

  // Note refs ![[note]] → removed (already expanded by assembler)
  // But in case there are leftovers:
  tex = tex.replace(/!?\[\[([^\]]+)\]\]/g, "");

  // Horizontal rules
  tex = tex.replace(/^---+$/gm, "\hrulefill\\n");

  // Blockquotes > text
  tex = tex.replace(/^\u003e\s+(.+)$/gm, (_m, text) => {
    return `\begin{quote}\n${escapeLatex(text)}\n\end{quote}`;
  });

  // Multiple consecutive newlines → single paragraph break
  tex = tex.replace(/\n{3,}/g, "\n\n");

  return tex;
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
 * Escape special LaTeX characters in text.
 */
function escapeLatex(text: string): string {
  return text
    .replace(/\\/g, "\\\\textbackslash{}")
    .replace(/\{/g, "\\{")
    .replace(/\}/g, "\\}")
    .replace(/\$/g, "\\$")
    .replace(/&/g, "\\&")
    .replace(/#/g, "\\#")
    .replace(/\^/g, "\\^{}")
    .replace(/_/g, "\\_")
    .replace(/%/g, "\\%")
    .replace(/~/g, "\\textasciitilde{}")
    .replace(/"/g, "''");
}
