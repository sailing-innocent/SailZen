/**
 * @file astLatexTransformer.test.ts
 * @brief Unit tests for AST-based LaTeX transformer
 */

import { mdastToLatex } from "../astLatexTransformer";
import { DocProfile } from "@saili/common-all";

describe("astLatexTransformer", () => {
  const makeProfile = (overrides?: Partial<DocProfile>): DocProfile => ({
    rootNoteId: "root",
    rootNoteFname: "project.test",
    exports: [{ format: "latex" }],
    meta: {},
    includes: [],
    discovered: [],
    citations: [],
    assets: [],
    ...overrides,
  });

  it("should convert headings to LaTeX section commands", () => {
    const ast = {
      type: "root",
      children: [
        { type: "heading", depth: 1, children: [{ type: "text", value: "Intro" }] },
        { type: "heading", depth: 2, children: [{ type: "text", value: "Method" }] },
      ],
    };
    const result = mdastToLatex(ast as any, makeProfile(), {});
    expect(result).toContain("\\section{Intro}");
    expect(result).toContain("\\subsection{Method}");
  });

  it("should convert emphasis and strong", () => {
    const ast = {
      type: "root",
      children: [
        {
          type: "paragraph",
          children: [
            { type: "emphasis", children: [{ type: "text", value: "italic" }] },
            { type: "text", value: " and " },
            { type: "strong", children: [{ type: "text", value: "bold" }] },
          ],
        },
      ],
    };
    const result = mdastToLatex(ast as any, makeProfile(), {});
    expect(result).toContain("\\textit{italic}");
    expect(result).toContain("\\textbf{bold}");
  });

  it("should convert sailzenCite to \\cite", () => {
    const ast = {
      type: "root",
      children: [
        {
          type: "paragraph",
          children: [
            { type: "text", value: "See " },
            { type: "sailzenCite", keys: ["foo", "bar"] },
          ],
        },
      ],
    };
    const result = mdastToLatex(ast as any, makeProfile(), {});
    expect(result).toContain("\\cite{foo, bar}");
  });

  it("should convert sailzenFigure to figure environment", () => {
    const ast = {
      type: "root",
      children: [
        {
          type: "sailzenFigure",
          caption: "Overview",
          src: "fig_overview",
          options: { label: "fig:overview", width: "0.8\\textwidth" },
        },
      ],
    };
    const result = mdastToLatex(ast as any, makeProfile(), {});
    expect(result).toContain("\\begin{figure}");
    expect(result).toContain("\\includegraphics");
    expect(result).toContain("Overview");
    expect(result).toContain("fig:overview");
  });

  it("should convert sailzenMathEnv to theorem environment", () => {
    const ast = {
      type: "root",
      children: [
        {
          type: "sailzenMathEnv",
          envType: "theorem",
          title: "Main Result",
          label: "thm:main",
          children: [
            { type: "paragraph", children: [{ type: "text", value: "Proof follows." }] },
          ],
        },
      ],
    };
    const result = mdastToLatex(ast as any, makeProfile(), {});
    expect(result).toContain("\\begin{theorem}[Main Result]");
    expect(result).toContain("\\label{thm:main}");
    expect(result).toContain("\\end{theorem}");
  });

  it("should strip non-latex if-format blocks", () => {
    const ast = {
      type: "root",
      children: [
        {
          type: "sailzenIfFormat",
          format: "typst",
          children: [{ type: "paragraph", children: [{ type: "text", value: "Typst only" }] }],
        },
        {
          type: "sailzenIfFormat",
          format: "latex",
          children: [{ type: "paragraph", children: [{ type: "text", value: "LaTeX only" }] }],
        },
      ],
    };
    const result = mdastToLatex(ast as any, makeProfile(), {});
    expect(result).not.toContain("Typst only");
    expect(result).toContain("LaTeX only");
  });
});
