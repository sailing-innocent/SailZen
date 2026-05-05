/**
 * @file integration.test.ts
 * @brief Integration test simulating the real project.testdoc.paper export
 */

import { NoteProps, NotePropsByIdDict } from "@saili/common-all";
import { assembleDocument } from "../documentAssembler";
import { generateLatex } from "../latexBackend";
import { resolveProfile } from "../profileResolver";

const makeNote = (id: string, fname: string, body: string, custom?: any): NoteProps =>
  ({
    id,
    fname,
    body,
    custom,
    title: fname,
    vault: { name: "vault", fsPath: "/vault" },
    type: "note",
    desc: "",
    links: [],
    anchors: {},
    children: [],
    parent: null,
    data: {},
    updated: 0,
    created: 0,
  } as NoteProps);

describe("DocEngine Integration", () => {
  it("should generate correct LaTeX for project.testdoc.paper scenario", async () => {
    const root = makeNote(
      "PcnVj4GZBt7O3HTrwqdFq",
      "project.testdoc.paper",
      "# Abstract\n\nThis is a test paper for the SailZen Doc Engine MVP. It demonstrates the complete pipeline from note frontmatter to LaTeX output.\n\n![[project.testdoc.content.intro]]\n\n![[project.testdoc.content.method]]\n\n# Conclusion\n\nThe doc engine successfully assembled this paper from multiple compose notes ::cite[foo, bar].",
      {
        doc: {
          role: "standalone",
          project: "project.testdoc",
          exports: [{ format: "latex", template: "article" }],
          meta: {
            title: "Test Paper for Doc Engine MVP",
            authors: [{ name: "Test Author", affiliation: "SailZen Lab" }],
            keywords: ["test", "doc-engine", "mvp"],
          },
        },
      }
    );

    const intro = makeNote(
      "PcnVj4GZBt9O3HTrwqcFq",
      "project.testdoc.content.intro",
      '# Introduction\n\nThis is the introduction section of the test paper. It should appear as `\\section{Introduction}` in the LaTeX output.\n\nWe can cite references using the custom directive: ::cite[foo].\n\n## Motivation\n\nThe motivation behind the Doc Engine is to enable seamless publication from structured notes ::cite[foo].\n\n::figure[Overview of the proposed pipeline](fig_pipeline){width="0.8\\linewidth"}',
      {
        doc: { role: "compose", project: "project.testdoc", order: 1 },
      }
    );

    const method = makeNote(
      "PcnVk9GZBt7O3HTrwqcFq",
      "project.testdoc.content.method",
      '# Methodology\n\nThis section describes the methodology. It contains nested references and multiple citations.\n\n## Design\n\nOur design follows a pipeline architecture ::cite[bar].\n\n```python\ndef assemble(profile, notes):\n    body = expand_refs(profile.root, notes)\n    for note in profile.discovered:\n        body += "\\n\\n" + expand_refs(note, notes)\n    return body\n```\n\n## Implementation\n\nThe implementation uses recursive expansion for note references.\n\n$$E = mc^2$$\n\nThis is a block math equation that should be preserved in LaTeX.',
      {
        doc: { role: "compose", project: "project.testdoc", order: 2 },
      }
    );

    const figNote = makeNote(
      "fig-pipeline-001",
      "project.testdoc.fig.pipeline",
      "Asset note for pipeline figure.",
      {
        doc: {
          role: "asset",
          asset: {
            path: "assets/images/fig_pipeline.png",
            width: "0.8\\linewidth",
            caption: "Overview of the proposed pipeline",
            label: "fig:pipeline",
          },
        },
      }
    );

    const notesById: NotePropsByIdDict = {
      [root.id]: root,
      [intro.id]: intro,
      [method.id]: method,
      [figNote.id]: figNote,
    };

    const profile = resolveProfile(root, notesById);
    // Both compose notes are auto-discovered AND referenced via ![[...]]
    expect(profile.discovered).toContain("project.testdoc.content.intro");
    expect(profile.discovered).toContain("project.testdoc.content.method");

    const assembled = assembleDocument(profile, notesById);

    // KEY ASSERTION 1: No duplicate content
    // Count occurrences of "Introduction" heading in assembled body
    const introHeadings = (assembled.body.match(/^#+ Introduction$/gm) || []).length;
    expect(introHeadings).toBe(1);

    const methodHeadings = (assembled.body.match(/^#+ Methodology$/gm) || []).length;
    expect(methodHeadings).toBe(1);

    // KEY ASSERTION 2: Heading depths are correct
    // Root # Abstract stays as # Abstract
    expect(assembled.body).toContain("# Abstract");
    // Intro # Introduction becomes ## Introduction (embedded under root)
    expect(assembled.body).toContain("## Introduction");
    // Intro ## Motivation becomes ### Motivation
    expect(assembled.body).toContain("### Motivation");
    // Method # Methodology becomes ## Methodology
    expect(assembled.body).toContain("## Methodology");
    // Method ## Design becomes ### Design
    expect(assembled.body).toContain("### Design");
    // Method ## Implementation becomes ### Implementation
    expect(assembled.body).toContain("### Implementation");
    // Root # Conclusion stays as # Conclusion
    expect(assembled.body).toContain("# Conclusion");

    const exportConfig = profile.exports[0];
    const generated = await generateLatex(assembled, profile, exportConfig, notesById, "/ws/root");

    // KEY ASSERTION 3: LaTeX structure is correct
    expect(generated.mainContent).toContain("\\documentclass{article}");
    // Title should come from root note frontmatter, not fname
    expect(generated.mainContent).toContain("\\title{Test Paper for Doc Engine MVP}");
    expect(generated.mainContent).not.toContain("\\title{project.testdoc.paper}");
    expect(generated.mainContent).toContain("\\author{Test Author \\\\ SailZen Lab}");

    // Sections should be correct (no duplication)
    const sections = generated.mainContent.match(/\\section\{([^}]+)\}/g) || [];
    expect(sections).toContain("\\section{Abstract}");
    expect(sections).toContain("\\section{Conclusion}");
    // Introduction and Methodology should be subsections because they are embedded
    expect(generated.mainContent).toContain("\\subsection{Introduction}");
    expect(generated.mainContent).toContain("\\subsection{Methodology}");

    // KEY ASSERTION 4: Code block is preserved as verbatim
    expect(generated.mainContent).toContain("\\begin{verbatim}");
    expect(generated.mainContent).toContain("\\end{verbatim}");
    // The code inside verbatim should NOT be escaped with \textbackslash
    expect(generated.mainContent).not.toContain("\\textbackslash{}n");

    // KEY ASSERTION 5: Inline code with backslash is preserved reasonably
    // \section{Introduction} inside \texttt becomes \textbackslash\{\}section\{Introduction\}
    expect(generated.mainContent).toContain("\\texttt{\\textbackslash\\{\\}section\\{Introduction\\}}");

    // KEY ASSERTION 6: Math is preserved
    expect(generated.mainContent).toContain("\\[");
    expect(generated.mainContent).toContain("E = mc^2");
    expect(generated.mainContent).toContain("\\]");

    // KEY ASSERTION 7: Figure directive
    expect(generated.mainContent).toContain("\\begin{figure}");
    expect(generated.mainContent).toContain("\\caption{Overview of the proposed pipeline}");
    expect(generated.mainContent).toContain("\\includegraphics[width=0.8\\linewidth]{../figures/fig_pipeline.png}");

    // KEY ASSERTION 8: Citations
    expect(generated.mainContent).toContain("\\cite{foo}");
    expect(generated.mainContent).toContain("\\cite{bar}");

    // KEY ASSERTION 9: Bibliography file uses correct name
    expect(generated.extraFiles.some((f) => f.path === "ref.bib")).toBe(true);

    // KEY ASSERTION 10: latexmkrc is generated for user-driven compilation
    const latexmkrc = generated.extraFiles.find((f) => f.path === "latexmkrc");
    expect(latexmkrc).toBeDefined();
    expect(latexmkrc!.content).toContain("latexmk");
    expect(latexmkrc!.content).toContain("$pdf_mode");
    expect(latexmkrc!.content).toContain("$bibtex");

    // KEY ASSERTION 11: Asset files are resolved for project-level figures/ directory
    expect(generated.assetFiles.length).toBeGreaterThan(0);
    const figAssetFile = generated.assetFiles.find((a) => a.destPath.includes("fig_pipeline"));
    expect(figAssetFile).toBeDefined();
    expect(figAssetFile!.destPath).toBe("figures/fig_pipeline.png");
    // srcPath should be resolved relative to wsRoot (platform-specific separators)
    expect(figAssetFile!.srcPath.replace(/\\/g, "/")).toContain("assets/images/fig_pipeline.png");
  });
});
