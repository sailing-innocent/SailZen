/**
 * @file latexBackend.test.ts
 * @brief Unit tests for DocEngine LaTeX Backend
 * @description Validates markdown-to-LaTeX conversion, cite/figure directives, and BibTeX generation.
 */

import { AssembledDocument, DocProfile, DocExportConfig, NoteProps, NotePropsByIdDict } from "@saili/common-all";
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
  });
});
