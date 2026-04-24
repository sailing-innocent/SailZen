import {
  AssembledDocument,
  DocExportConfig,
  DocProfile,
  NoteProps,
  NotePropsByIdDict,
} from "@saili/common-all";
import { generateMarkdown } from "../markdownBackend";

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
    tags: [],
  } as NoteProps);

const makeAssembled = (body: string): AssembledDocument => ({
  body,
  headingOffsets: {},
  includedNotes: [],
  unresolvedRefs: [],
});

const makeProfile = (overrides?: Partial<DocProfile>): DocProfile => ({
  rootNoteId: "root-id",
  rootNoteFname: "blog.test.post",
  exports: [{ format: "markdown" }],
  meta: { title: "My Blog Post" },
  includes: [],
  discovered: [],
  citations: [],
  assets: [],
  ...overrides,
});

const exportConfig: DocExportConfig = { format: "markdown" };

describe("markdownBackend", () => {
  describe("generateMarkdown", () => {
    it("produces ext=md and wraps content with frontmatter", async () => {
      const result = await generateMarkdown(
        makeAssembled("Hello world."),
        makeProfile(),
        exportConfig,
        {}
      );
      expect(result.ext).toBe("md");
      expect(result.mainContent).toContain("---");
      expect(result.mainContent).toContain('title: "My Blog Post"');
      expect(result.mainContent).toContain("Hello world.");
    });

    it("includes date field in frontmatter", async () => {
      const result = await generateMarkdown(
        makeAssembled("body"),
        makeProfile(),
        exportConfig,
        {}
      );
      expect(result.mainContent).toMatch(/date: \d{4}-\d{2}-\d{2}/);
    });

    it("includes description from profile.meta.abstract", async () => {
      const result = await generateMarkdown(
        makeAssembled("body"),
        makeProfile({ meta: { title: "T", abstract: "My abstract" } }),
        exportConfig,
        {}
      );
      expect(result.mainContent).toContain('description: "My abstract"');
    });

    it("includes tags from root note", async () => {
      const rootNote = makeNote("root-id", "blog.test.post");
      (rootNote as any).tags = ["typescript", "vscode"];
      const notesById: NotePropsByIdDict = { "root-id": rootNote };

      const result = await generateMarkdown(
        makeAssembled("body"),
        makeProfile(),
        exportConfig,
        notesById
      );
      expect(result.mainContent).toContain('"typescript"');
      expect(result.mainContent).toContain('"vscode"');
    });

    it("has empty extraFiles and assetFiles", async () => {
      const result = await generateMarkdown(
        makeAssembled("body"),
        makeProfile(),
        exportConfig,
        {}
      );
      expect(result.extraFiles).toHaveLength(0);
      expect(result.assetFiles).toHaveLength(0);
    });
  });

  describe("::cite conversion", () => {
    it("converts ::cite[key1, key2] to [key1, key2]", async () => {
      const result = await generateMarkdown(
        makeAssembled("See ::cite[nerf, gaussian] for details."),
        makeProfile(),
        exportConfig,
        {}
      );
      expect(result.mainContent).toContain("[nerf, gaussian]");
      expect(result.mainContent).not.toContain("::cite");
    });

    it("preserves ::cite keys inside code blocks", async () => {
      const result = await generateMarkdown(
        makeAssembled("```\n::cite[key]\n```"),
        makeProfile(),
        exportConfig,
        {}
      );
      expect(result.mainContent).toContain("::cite[key]");
    });
  });

  describe("::figure conversion", () => {
    it("converts ::figure to standard Markdown image", async () => {
      const result = await generateMarkdown(
        makeAssembled("::figure[My caption](fig_teaser)"),
        makeProfile(),
        exportConfig,
        {}
      );
      expect(result.mainContent).toContain("![My caption](fig_teaser)");
      expect(result.mainContent).not.toContain("::figure");
    });

    it("resolves asset path from assetMap when available", async () => {
      const profile = makeProfile({
        resolvedAssets: [
          {
            ref: "fig_teaser",
            path: "figures/teaser.png",
            caption: "Teaser",
          },
        ],
      });
      const result = await generateMarkdown(
        makeAssembled("::figure[Caption](fig_teaser)"),
        profile,
        exportConfig,
        {},
        "/workspace"
      );
      expect(result.mainContent).toContain("teaser.png");
    });

    it("resolves vault-relative path to absolute when wsRoot provided", async () => {
      const result = await generateMarkdown(
        makeAssembled("::figure[Cap](assets/img.png)"),
        makeProfile(),
        exportConfig,
        {},
        "/workspace"
      );
      expect(result.mainContent).toContain("/workspace/assets/img.png");
    });
  });

  describe("::ref removal", () => {
    it("removes ::ref[label] entirely", async () => {
      const result = await generateMarkdown(
        makeAssembled("See ::ref[fig:teaser] above."),
        makeProfile(),
        exportConfig,
        {}
      );
      expect(result.mainContent).not.toContain("::ref");
      expect(result.mainContent).toContain("See  above.");
    });
  });

  describe("::table conversion", () => {
    it("converts ::table to bold caption + markdown table", async () => {
      const body =
        "::table[Results](tab:results)\n| A | B |\n|---|---|\n| 1 | 2 |\n";
      const result = await generateMarkdown(
        makeAssembled(body),
        makeProfile(),
        exportConfig,
        {}
      );
      expect(result.mainContent).toContain("**Results**");
      expect(result.mainContent).toContain("| A | B |");
      expect(result.mainContent).not.toContain("::table");
    });
  });

  describe("::theorem / ::proof conversion", () => {
    it("converts ::theorem to blockquote bold", async () => {
      const body =
        "::theorem[Consistency]{label: \"thm\"}\nAll gaussians are consistent.\n::end";
      const result = await generateMarkdown(
        makeAssembled(body),
        makeProfile(),
        exportConfig,
        {}
      );
      expect(result.mainContent).toContain("> **Theorem");
      expect(result.mainContent).not.toContain("::theorem");
      expect(result.mainContent).not.toContain("::end");
    });

    it("converts ::proof to blockquote with QED symbol", async () => {
      const body = "::proof\nBy induction.\n::end";
      const result = await generateMarkdown(
        makeAssembled(body),
        makeProfile(),
        exportConfig,
        {}
      );
      expect(result.mainContent).toContain("> *Proof.*");
      expect(result.mainContent).toContain("∎");
    });
  });

  describe("::algorithm conversion", () => {
    it("converts ::algorithm to fenced code block", async () => {
      const body =
        "::algorithm[Prefix Sum]\n1. Up-sweep phase\n2. Down-sweep phase\n::end";
      const result = await generateMarkdown(
        makeAssembled(body),
        makeProfile(),
        exportConfig,
        {}
      );
      expect(result.mainContent).toContain("```");
      expect(result.mainContent).toContain("Algorithm: Prefix Sum");
      expect(result.mainContent).not.toContain("::algorithm");
    });
  });

  describe("::if-format conditional blocks", () => {
    it("keeps ::if-format[markdown] content", async () => {
      const body =
        "::if-format[markdown]\nThis is markdown-specific.\n::end";
      const result = await generateMarkdown(
        makeAssembled(body),
        makeProfile(),
        exportConfig,
        {}
      );
      expect(result.mainContent).toContain("This is markdown-specific.");
    });

    it("strips ::if-format[latex] content", async () => {
      const body =
        "::if-format[latex]\nThis is LaTeX-only.\n::end";
      const result = await generateMarkdown(
        makeAssembled(body),
        makeProfile(),
        exportConfig,
        {}
      );
      expect(result.mainContent).not.toContain("This is LaTeX-only.");
    });

    it("strips ::if-format[typst] content", async () => {
      const body = "::if-format[typst]\nTypst only.\n::end";
      const result = await generateMarkdown(
        makeAssembled(body),
        makeProfile(),
        exportConfig,
        {}
      );
      expect(result.mainContent).not.toContain("Typst only.");
    });
  });

  describe("wikilink conversion", () => {
    it("converts [[note.fname]] to note title when found", async () => {
      const noteA = makeNote("a1", "project.alpha");
      noteA.title = "Alpha Project";
      const notesById: NotePropsByIdDict = { a1: noteA };

      const result = await generateMarkdown(
        makeAssembled("See [[project.alpha]] for more."),
        makeProfile(),
        exportConfig,
        notesById
      );
      expect(result.mainContent).toContain("Alpha Project");
      expect(result.mainContent).not.toContain("[[");
    });

    it("falls back to last fname segment when note not found", async () => {
      const result = await generateMarkdown(
        makeAssembled("See [[some.deep.note]]."),
        makeProfile(),
        exportConfig,
        {}
      );
      expect(result.mainContent).toContain("note");
      expect(result.mainContent).not.toContain("[[");
    });

    it("removes ![[note.ref]] embed refs", async () => {
      const result = await generateMarkdown(
        makeAssembled("Before ![[some.note]] After"),
        makeProfile(),
        exportConfig,
        {}
      );
      expect(result.mainContent).not.toContain("![[");
      expect(result.mainContent).toContain("Before");
      expect(result.mainContent).toContain("After");
    });
  });

  describe("pass-through content", () => {
    it("preserves code blocks unchanged", async () => {
      const code = "```typescript\nconst x = 1;\n```";
      const result = await generateMarkdown(
        makeAssembled(code),
        makeProfile(),
        exportConfig,
        {}
      );
      expect(result.mainContent).toContain("```typescript\nconst x = 1;\n```");
    });

    it("preserves inline math $...$", async () => {
      const result = await generateMarkdown(
        makeAssembled("The formula $E = mc^2$ is famous."),
        makeProfile(),
        exportConfig,
        {}
      );
      expect(result.mainContent).toContain("$E = mc^2$");
    });

    it("preserves block math $$...$$", async () => {
      const result = await generateMarkdown(
        makeAssembled("$$\n\\int_0^1 f(x) dx\n$$"),
        makeProfile(),
        exportConfig,
        {}
      );
      expect(result.mainContent).toContain("$$\n\\int_0^1 f(x) dx\n$$");
    });

    it("preserves standard markdown headings", async () => {
      const result = await generateMarkdown(
        makeAssembled("## Section\n\nContent."),
        makeProfile(),
        exportConfig,
        {}
      );
      expect(result.mainContent).toContain("## Section");
    });
  });

  describe("optional references section", () => {
    it("appends references when appendReferences=true and citations exist", async () => {
      const bibNote = makeNote("bib1", "source.papers.nerf");
      bibNote.custom = {
        doc: {
          role: "bib",
          bibtex: {
            type: "article",
            key: "nerf",
            fields: { title: "NeRF: Representing Scenes as Neural Radiance Fields" },
          },
        },
      };
      const notesById: NotePropsByIdDict = { bib1: bibNote };

      const result = await generateMarkdown(
        makeAssembled("See ::cite[nerf]."),
        makeProfile({ citations: ["nerf"] }),
        { format: "markdown", vars: { appendReferences: true } },
        notesById
      );
      expect(result.mainContent).toContain("## References");
      expect(result.mainContent).toContain("NeRF");
    });

    it("does not append references when appendReferences is not set", async () => {
      const result = await generateMarkdown(
        makeAssembled("text"),
        makeProfile({ citations: ["nerf"] }),
        exportConfig,
        {}
      );
      expect(result.mainContent).not.toContain("## References");
    });
  });
});
