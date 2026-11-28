/**
 * @file latexUtils.ts
 * @brief Shared LaTeX escaping utilities for SailZen Doc Engine
 * @description Consolidates escapeLatex and escapeLatexInlineCode to avoid
 *   duplication across latexBackend, astLatexTransformer, and templateEngine.
 */

/**
 * Escape plain text for LaTeX.
 * Intentionally NOT escaping backslash here – all legitimate LaTeX commands
 * must be protected before this function runs.
 */
export function escapeLatex(text: string): string {
  return (
    text
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
 * Escape inline code for LaTeX \texttt{}.
 * Also escapes backslash because inline code is literal.
 */
export function escapeLatexInlineCode(text: string): string {
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
