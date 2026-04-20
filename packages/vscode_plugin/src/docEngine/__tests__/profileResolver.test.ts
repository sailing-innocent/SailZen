/**
 * @file profileResolver.test.ts
 * @brief Unit tests for DocEngine ProfileResolver
 * @description Validates profile resolution from note frontmatter and auto-discovery of compose notes.
 */

import { NoteProps, NotePropsByIdDict } from "@saili/common-all";
import { resolveProfile, extractCitations, extractAssetRefs } from "../profileResolver";

describe("profileResolver", () => {
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

  describe("resolveProfile", () => {
    it("should resolve a standalone note with default latex export", () => {
      const root = makeNote("root-id", "project.test.paper", {
        doc: { role: "standalone", project: "project.test" },
      });
      const profile = resolveProfile(root, {});
      expect(profile.rootNoteId).toBe("root-id");
      expect(profile.rootNoteFname).toBe("project.test.paper");
      expect(profile.exports).toEqual([{ format: "latex", template: "article" }]);
    });

    it("should auto-discover compose notes in the same project", () => {
      const root = makeNote("root-id", "project.test.paper", {
        doc: { role: "standalone", project: "project.test", exports: [{ format: "latex", template: "acmart" }] },
      });
      const intro = makeNote("intro-id", "project.test.content.intro", {
        doc: { role: "compose", project: "project.test", order: 1 },
      });
      const method = makeNote("method-id", "project.test.content.method", {
        doc: { role: "compose", project: "project.test", order: 2 },
      });
      const other = makeNote("other-id", "other.project.note", {
        doc: { role: "compose", project: "other.project", order: 1 },
      });

      const notes: NotePropsByIdDict = {
        [root.id]: root,
        [intro.id]: intro,
        [method.id]: method,
        [other.id]: other,
      };

      const profile = resolveProfile(root, notes);
      expect(profile.discovered).toEqual([
        "project.test.content.intro",
        "project.test.content.method",
      ]);
      expect(profile.exports[0].format).toBe("latex");
      expect(profile.exports[0].template).toBe("acmart");
    });

    it("should sort discovered notes by order, then by fname", () => {
      const root = makeNote("root-id", "project.test.paper", {
        doc: { role: "standalone", project: "project.test" },
      });
      const b = makeNote("b-id", "project.test.b", {
        doc: { role: "compose", project: "project.test", order: 2 },
      });
      const a = makeNote("a-id", "project.test.a", {
        doc: { role: "compose", project: "project.test", order: 1 },
      });
      const c = makeNote("c-id", "project.test.c", {
        doc: { role: "compose", project: "project.test" }, // no order, defaults to Infinity
      });

      const notes: NotePropsByIdDict = { [root.id]: root, [b.id]: b, [a.id]: a, [c.id]: c };
      const profile = resolveProfile(root, notes);
      expect(profile.discovered).toEqual(["project.test.a", "project.test.b", "project.test.c"]);
    });

    it("should extract citations and assets from root body", () => {
      const root = makeNote("root-id", "project.test.paper", {
        doc: { role: "standalone", project: "project.test" },
      });
      root.body = "See ::cite[foo, bar] and ::figure[Teaser](fig_teaser){width=\\linewidth}.";
      const profile = resolveProfile(root, { [root.id]: root });
      expect(profile.citations).toContain("foo");
      expect(profile.citations).toContain("bar");
      expect(profile.assets).toContain("fig_teaser");
    });
  });

  describe("extractCitations", () => {
    it("should extract keys from ::cite[foo, bar]", () => {
      expect(extractCitations("::cite[foo, bar]")).toEqual(["foo", "bar"]);
    });
    it("should handle spaces and duplicates", () => {
      expect(extractCitations("::cite[ foo ] and ::cite[foo]")).toEqual(["foo"]);
    });
    it("should return empty array when no citations", () => {
      expect(extractCitations("No citations here.")).toEqual([]);
    });
  });

  describe("extractAssetRefs", () => {
    it("should extract src from ::figure[caption](src)", () => {
      expect(extractAssetRefs("::figure[Teaser](fig1)")).toEqual(["fig1"]);
    });
    it("should handle optional opts", () => {
      expect(extractAssetRefs("::figure[Table](tab1){columns=3}")).toEqual(["tab1"]);
    });
    it("should return empty array when no figures", () => {
      expect(extractAssetRefs("No figures here.")).toEqual([]);
    });
  });

  describe("extractTableRefs", () => {
    it("should extract label from ::table[caption](label)", () => {
      expect(extractTableRefs("::table[Results](tab:results)")).toEqual(["tab:results"]);
    });
    it("should handle optional opts", () => {
      expect(extractTableRefs("::table[Comparison](tab:compare){columns=lcc}")).toEqual(["tab:compare"]);
    });
    it("should return empty array when no tables", () => {
      expect(extractTableRefs("No tables here.")).toEqual([]);
    });
  });

  describe("extractMathEnvs", () => {
    it("should extract theorem and proof", () => {
      const body = "::theorem[Foo]\n...\n::end\n::proof\n...\n::end";
      expect(extractMathEnvs(body)).toEqual(["theorem", "proof"]);
    });
    it("should extract multiple distinct envs", () => {
      const body = "::definition[Def]\n::lemma[Lem]\n::corollary[Cor]\n::proposition[Prop]\n::remark[Rem]";
      expect(extractMathEnvs(body)).toEqual(["definition", "lemma", "corollary", "proposition", "remark"]);
    });
  });
});
