/**
 * @file latexBackend.test.ts
 * @brief Unit tests for DocEngine LaTeX Backend
 * @description Validates markdown-to-LaTeX conversion, cite/figure/table directives,
 *   math environments, algorithms, conditionals, lists, footnotes, and BibTeX generation.
 */

import {
  AssembledDocument,
  DocProfile,
  DocExportConfig,
  NoteProps,
  NotePropsByIdDict,
} from "@saili/common-all";
import { generateLatex } from "../latexBackend";

describe("latexBackend", () => {
  const makeNote = (id: string, fname: string, custom?: any): NoteProps =>
    ({
      id,
      fname,
      custom,
      title: fname,
      vault: { name: "vault", fsPath: "/vault" },
      type: "note",
      desc: "",
      links: [],
      anchors: {},
      children: [],
      parent: null,
      body: "",
      data: {},
      updated: 0,
      created: 0,
    } as NoteProps);

  describe("generateLatex", () => {
    it("should generate a main.tex with documentclass", () => {
      const assembled: AssembledDocument = {
        body: "# Hello World\n\nThis is a test.",
        headingOffsets: {},
        includedNotes: [],
        unresolvedRefs: [],
      };
      const profile: DocProfile = {
        rootNoteId: "root-id",
        rootNoteFname: "project.test.paper",
        exports: [{ format: "latex", template: "article" }],
        meta: { title: "Test Paper" },
        includes: [],
        discovered: [],
        citations: [],
        assets: [],
      };
      const exportConfig: DocExportConfig = { format: "latex", template: "article" };

      const result = generateLatex(assembled, profile, exportConfig, {});
      expect(result.ext).toBe("tex");
      expect(result.mainContent).toContain("\\documentclass{article}");
      expect(result.mainContent).toContain("\\title{Test Paper}");
      expect(result.mainContent).toContain("\\section{Hello World}");
    });

    it("should use acmart-sigconf template when requested", () => {
      const assembled: AssembledDocument = {
        body: "# Intro\n\nHello.",
        headingOffsets: {},
        includedNotes: [],
        unresolvedRefs: [],
      };
      const profile: DocProfile = {
        rootNoteId: "root-id",
        rootNoteFname: "project.test.paper",
        exports: [{ format: "latex", template: "acmart-sigconf" }],
        meta: { title: "ACM Paper" },
        includes: [],
        discovered: [],
        citations: [],
        assets: [],
      };
      const exportConfig: DocExportConfig = { format: "latex", template: "acmart-sigconf" };

      const result = generateLatex(assembled, profile, exportConfig, {});
      expect(result.mainContent).toContain("\\documentclass[sigconf,authordraft]{acmart}");
      expect(result.meta.templateUsed).toBe("acmart-sigconf");
    });

    it("should convert ::cite[keys] to \\cite{keys}", () => {
      const assembled: AssembledDocument = {
        body: "As shown in prior work ::cite[foo, bar].",
        headingOffsets: {},
        includedNotes: [],
        unresolvedRefs: [],
      };
      const profile: DocProfile = {
        rootNoteId: "root-id",
        rootNoteFname: "project.test.paper",
        exports: [{ format: "latex" }],
        meta: {},
        includes: [],
        discovered: [],
        citations: ["foo", "bar"],
        assets: [],
      };
      const exportConfig: DocExportConfig = { format: "latex" };

      const result = generateLatex(assembled, profile, exportConfig, {});
      expect(result.mainContent).toContain("\\cite{foo, bar}");
    });

    it("should convert ::figure to figure environment", () => {
      const assembled: AssembledDocument = {
        body: "::figure[Overview](fig_overview){width=0.8\\textwidth}",
        headingOffsets: {},
        includedNotes: [],
        unresolvedRefs: [],
      };
      const profile: DocProfile = {
        rootNoteId: "root-id",
        rootNoteFname: "project.test.paper",
        exports: [{ format: "latex" }],
        meta: {},
        includes: [],
        discovered: [],
        citations: [],
        assets: [],
      };
      const exportConfig: DocExportConfig = { format: "latex" };

      const result = generateLatex(assembled, profile, exportConfig, {});
      expect(result.mainContent).toContain("\\begin{figure}");
      expect(result.mainContent).toContain("\\includegraphics");
      expect(result.mainContent).toContain("Overview");
    });

    it("should convert ::table with markdown table to table environment", () => {
      const assembled: AssembledDocument = {
        body: "::table[Comparison](tab:compare){columns=lcc}\n| A | B | C |\n|---|---|---|\n| 1 | 2 | 3 |",
        headingOffsets: {},
        includedNotes: [],
        unresolvedRefs: [],
      };
      const profile: DocProfile = {
        rootNoteId: "root-id",
        rootNoteFname: "project.test.paper",
        exports: [{ format: "latex" }],
        meta: {},
        includes: [],
        discovered: [],
        citations: [],
        assets: [],
      };
      const exportConfig: DocExportConfig = { format: "latex" };

      const result = generateLatex(assembled, profile, exportConfig, {});
      expect(result.mainContent).toContain("\\begin{table}");
      expect(result.mainContent).toContain("\\caption{Comparison}");
      expect(result.mainContent).toContain("\\label{tab:compare}");
      expect(result.mainContent).toContain("\\begin{tabular}");
      expect(result.mainContent).toContain("\\hline");
    });

    it("should convert standalone markdown table to tabular", () => {
      const assembled: AssembledDocument = {
        body: "| A | B |\n|---|---|\n| 1 | 2 |",
        headingOffsets: {},
        includedNotes: [],
        unresolvedRefs: [],
      };
      const profile: DocProfile = {
        rootNoteId: "root-id",
        rootNoteFname: "project.test.paper",
        exports: [{ format: "latex" }],
        meta: {},
        includes: [],
        discovered: [],
        citations: [],
        assets: [],
      };
      const exportConfig: DocExportConfig = { format: "latex" };

      const result = generateLatex(assembled, profile, exportConfig, {});
      expect(result.mainContent).toContain("\\begin{tabular}");
      expect(result.mainContent).toContain("\\hline");
    });

    it("should convert ::theorem to theorem environment", () => {
      const assembled: AssembledDocument = {
        body: '::theorem[Feature Consistency]{label: "thm:consistency"}\nUnder the Markov blanket assumption...\n::end',
        headingOffsets: {},
        includedNotes: [],
        unresolvedRefs: [],
      };
      const profile: DocProfile = {
        rootNoteId: "root-id",
        rootNoteFname: "project.test.paper",
        exports: [{ format: "latex" }],
        meta: {},
        includes: [],
        discovered: [],
        citations: [],
        assets: [],
      };
      const exportConfig: DocExportConfig = { format: "latex" };

      const result = generateLatex(assembled, profile, exportConfig, {});
      expect(result.mainContent).toContain("\\begin{theorem}[Feature Consistency]");
      expect(result.mainContent).toContain("\\label{thm:consistency}");
      expect(result.mainContent).toContain("\\end{theorem}");
    });

    it("should convert ::proof to proof environment", () => {
      const assembled: AssembledDocument = {
        body: "::proof\nThe likelihood term decomposes as...\n::end",
        headingOffsets: {},
        includedNotes: [],
        unresolvedRefs: [],
      };
      const profile: DocProfile = {
        rootNoteId: "root-id",
        rootNoteFname: "project.test.paper",
        exports: [{ format: "latex" }],
        meta: {},
        includes: [],
        discovered: [],
        citations: [],
        assets: [],
      };
      const exportConfig: DocExportConfig = { format: "latex" };

      const result = generateLatex(assembled, profile, exportConfig, {});
      expect(result.mainContent).toContain("\\begin{proof}");
      expect(result.mainContent).toContain("\\end{proof}");
    });

    it("should convert ::definition to definition environment", () => {
      const assembled: AssembledDocument = {
        body: '::definition[Bayesian GS]{label: "def:bigs"}\nGiven a set of 3D Gaussians...\n::end',
        headingOffsets: {},
        includedNotes: [],
        unresolvedRefs: [],
      };
      const profile: DocProfile = {
        rootNoteId: "root-id",
        rootNoteFname: "project.test.paper",
        exports: [{ format: "latex" }],
        meta: {},
        includes: [],
        discovered: [],
        citations: [],
        assets: [],
      };
      const exportConfig: DocExportConfig = { format: "latex" };

      const result = generateLatex(assembled, profile, exportConfig, {});
      expect(result.mainContent).toContain("\\begin{definition}[Bayesian GS]");
      expect(result.mainContent).toContain("\\label{def:bigs}");
      expect(result.mainContent).toContain("\\end{definition}");
    });

    it("should convert ::algorithm to algorithm environment", () => {
      const assembled: AssembledDocument = {
        body: '::algorithm[Parallel Prefix Sum]{label: "alg:prefix-sum"}\n::input[Array $A$ of length $n$]\n::output[Array $B$]\n1. Up-sweep: for $d = 0$ to $\log_2 n - 1$:\n   - parallel for $i = 0$ to $n-1$ by $2^{d+1}$:\n::end',
        headingOffsets: {},
        includedNotes: [],
        unresolvedRefs: [],
      };
      const profile: DocProfile = {
        rootNoteId: "root-id",
        rootNoteFname: "project.test.paper",
        exports: [{ format: "latex" }],
        meta: {},
        includes: [],
        discovered: [],
        citations: [],
        assets: [],
      };
      const exportConfig: DocExportConfig = { format: "latex" };

      const result = generateLatex(assembled, profile, exportConfig, {});
      expect(result.mainContent).toContain("\\begin{algorithm}");
      expect(result.mainContent).toContain("\\caption{Parallel Prefix Sum}");
      expect(result.mainContent).toContain("\\label{alg:prefix-sum}");
      expect(result.mainContent).toContain("\\Require Array $A$ of length $n$");
      expect(result.mainContent).toContain("\\Ensure Array $B$");
      expect(result.mainContent).toContain("\\State Up-sweep: for $d = 0$ to $\log_2 n - 1$:");
      expect(result.mainContent).toContain("\\end{algorithm}");
    });

    it("should keep ::if-format[latex] and strip others", () => {
      const assembled: AssembledDocument = {
        body: "::if-format[latex]\nKeep this.\n::end\n\n::if-format[slidev]\nRemove this.\n::end",
        headingOffsets: {},
        includedNotes: [],
        unresolvedRefs: [],
      };
      const profile: DocProfile = {
        rootNoteId: "root-id",
        rootNoteFname: "project.test.paper",
        exports: [{ format: "latex" }],
        meta: {},
        includes: [],
        discovered: [],
        citations: [],
        assets: [],
      };
      const exportConfig: DocExportConfig = { format: "latex" };

      const result = generateLatex(assembled, profile, exportConfig, {});
      expect(result.mainContent).toContain("Keep this.");
      expect(result.mainContent).not.toContain("Remove this.");
    });

    it("should convert ordered lists to enumerate", () => {
      const assembled: AssembledDocument = {
        body: "1. First item\n2. Second item\n3. Third item",
        headingOffsets: {},
        includedNotes: [],
        unresolvedRefs: [],
      };
      const profile: DocProfile = {
        rootNoteId: "root-id",
        rootNoteFname: "project.test.paper",
        exports: [{ format: "latex" }],
        meta: {},
        includes: [],
        discovered: [],
        citations: [],
        assets: [],
      };
      const exportConfig: DocExportConfig = { format: "latex" };

      const result = generateLatex(assembled, profile, exportConfig, {});
      expect(result.mainContent).toContain("\\begin{enumerate}");
      expect(result.mainContent).toContain("\\item First item");
      expect(result.mainContent).toContain("\\item Second item");
      expect(result.mainContent).toContain("\\end{enumerate}");
    });

    it("should convert footnotes", () => {
      const assembled: AssembledDocument = {
        body: "This is text[^1] with a footnote.\n\n[^1]: Footnote content here.",
        headingOffsets: {},
        includedNotes: [],
        unresolvedRefs: [],
      };
      const profile: DocProfile = {
        rootNoteId: "root-id",
        rootNoteFname: "project.test.paper",
        exports: [{ format: "latex" }],
        meta: {},
        includes: [],
        discovered: [],
        citations: [],
        assets: [],
      };
      const exportConfig: DocExportConfig = { format: "latex" };

      const result = generateLatex(assembled, profile, exportConfig, {});
      expect(result.mainContent).toContain("\\footnote{Footnote content here.}");
      expect(result.mainContent).not.toContain("[^1]:");
    });

    it("should generate ref.bib from citation keys and bib notes", () => {
      const bibNote = makeNote("bib-id", "source.papers.foo", {
        doc: {
          role: "bib",
          bibtex: {
            type: "article",
            key: "foo",
            fields: { title: "A Great Paper", author: "Foo, A.", year: "2024" },
          },
        },
      });
      const assembled: AssembledDocument = {
        body: "::cite[foo]",
        headingOffsets: {},
        includedNotes: [],
        unresolvedRefs: [],
      };
      const profile: DocProfile = {
        rootNoteId: "root-id",
        rootNoteFname: "project.test.paper",
        exports: [{ format: "latex" }],
        meta: {},
        includes: [],
        discovered: [],
        citations: ["foo"],
        assets: [],
      };
      const exportConfig: DocExportConfig = { format: "latex" };
      const notes: NotePropsByIdDict = { [bibNote.id]: bibNote };

      const result = generateLatex(assembled, profile, exportConfig, notes);
      const bibFile = result.extraFiles.find((f) => f.path === "ref.bib");
      expect(bibFile).toBeDefined();
      expect(bibFile!.content).toContain("@article{foo");
      expect(bibFile!.content).toContain("title = {A Great Paper}");
    });

    it("should generate placeholder bib entry for missing citations", () => {
      const assembled: AssembledDocument = {
        body: "::cite[missing]",
        headingOffsets: {},
        includedNotes: [],
        unresolvedRefs: [],
      };
      const profile: DocProfile = {
        rootNoteId: "root-id",
        rootNoteFname: "project.test.paper",
        exports: [{ format: "latex" }],
        meta: {},
        includes: [],
        discovered: [],
        citations: ["missing"],
        assets: [],
      };
      const exportConfig: DocExportConfig = { format: "latex" };

      const result = generateLatex(assembled, profile, exportConfig, {});
      const bibFile = result.extraFiles.find((f) => f.path === "ref.bib");
      expect(bibFile!.content).toContain("@misc{missing");
    });

    it("should preserve math blocks", () => {
      const assembled: AssembledDocument = {
        body: "$$E = mc^2$$",
        headingOffsets: {},
        includedNotes: [],
        unresolvedRefs: [],
      };
      const profile: DocProfile = {
        rootNoteId: "root-id",
        rootNoteFname: "project.test.paper",
        exports: [{ format: "latex" }],
        meta: {},
        includes: [],
        discovered: [],
        citations: [],
        assets: [],
      };
      const exportConfig: DocExportConfig = { format: "latex" };

      const result = generateLatex(assembled, profile, exportConfig, {});
      expect(result.mainContent).toContain("\\[");
      expect(result.mainContent).toContain("E = mc^2");
      expect(result.mainContent).toContain("\\]");
    });

    it("should escape LaTeX special characters", () => {
      const assembled: AssembledDocument = {
        body: "100% of users & 50$ spent on #1 item with 10^2 units.",
        headingOffsets: {},
        includedNotes: [],
        unresolvedRefs: [],
      };
      const profile: DocProfile = {
        rootNoteId: "root-id",
        rootNoteFname: "project.test.paper",
        exports: [{ format: "latex" }],
        meta: {},
        includes: [],
        discovered: [],
        citations: [],
        assets: [],
      };
      const exportConfig: DocExportConfig = { format: "latex" };

      const result = generateLatex(assembled, profile, exportConfig, {});
      expect(result.mainContent).toContain("\\%");
      expect(result.mainContent).toContain("\\&");
      expect(result.mainContent).toContain("\\$");
      expect(result.mainContent).toContain("\\#");
      expect(result.mainContent).toContain("\\^{}");
    });

    it("should split sections when splitSections is enabled", () => {
      const assembled: AssembledDocument = {
        body: "# Introduction\n\nIntro text.\n\n# Method\n\nMethod text.\n\n# Conclusion\n\nConclusion text.",
        headingOffsets: {},
        includedNotes: [],
        unresolvedRefs: [],
      };
      const profile: DocProfile = {
        rootNoteId: "root-id",
        rootNoteFname: "project.test.paper",
        exports: [{ format: "latex", template: "article" }],
        meta: { title: "Split Test" },
        includes: [],
        discovered: [],
        citations: [],
        assets: [],
      };
      const exportConfig: DocExportConfig = {
        format: "latex",
        template: "article",
        vars: { splitSections: true },
      };

      const result = generateLatex(assembled, profile, exportConfig, {});
      expect(result.sections).toBeDefined();
      expect(result.sections!.length).toBe(3);
      expect(result.sections![0].title).toBe("Introduction");
      expect(result.sections![0].fileName).toMatch(/^\d{2}_introduction\.tex$/);
      expect(result.sections![0].content).toContain("\\section{Introduction}");
      expect(result.mainContent).toContain("\\input{sections/");
      expect(result.mainContent).not.toContain("Intro text.");
    });

    it("should pass template variables to built-in templates", () => {
      const assembled: AssembledDocument = {
        body: "# Intro\n\nText.",
        headingOffsets: {},
        includedNotes: [],
        unresolvedRefs: [],
      };
      const profile: DocProfile = {
        rootNoteId: "root-id",
        rootNoteFname: "project.test.paper",
        exports: [{ format: "latex", template: "article" }],
        meta: {
          title: "Custom Title",
          authors: [{ name: "Alice", affiliation: "MIT" }],
          keywords: ["AI", "ML"],
        },
        includes: [],
        discovered: [],
        citations: [],
        assets: [],
      };
      const exportConfig: DocExportConfig = {
        format: "latex",
        template: "article",
        vars: { bibliographystyle: "alpha" },
      };

      const result = generateLatex(assembled, profile, exportConfig, {});
      expect(result.mainContent).toContain("\\title{Custom Title}");
      expect(result.mainContent).toContain("\\author{Alice \\\\ MIT}");
      expect(result.mainContent).toContain("\\textbf{Keywords:} AI, ML");
      expect(result.mainContent).toContain("\\bibliographystyle{alpha}");
    });
  });
});
