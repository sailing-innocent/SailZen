/**
 * @file documentAssembler.test.ts
 * @brief Unit tests for DocEngine DocumentAssembler
 * @description Validates recursive note-ref expansion and heading depth shifting.
 */

import { NoteProps, NotePropsByIdDict, DocProfile } from "@saili/common-all";
import { assembleDocument } from "../documentAssembler";

describe("documentAssembler", () => {
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

  describe("assembleDocument", () => {
    it("should expand note refs recursively", () => {
      const root = makeNote("root-id", "project.test.paper", "# Paper\n\n![[project.test.content.intro]]");
      const intro = makeNote("intro-id", "project.test.content.intro", "This is the introduction.");

      const notes: NotePropsByIdDict = { [root.id]: root, [intro.id]: intro };
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

      const assembled = assembleDocument(profile, notes);
      expect(assembled.body).toContain("This is the introduction.");
      expect(assembled.body).not.toContain("![[project.test.content.intro]]");
    });

    it("should append discovered compose notes in order", () => {
      const root = makeNote("root-id", "project.test.paper", "# Paper\n\nRoot content.");
      const intro = makeNote("intro-id", "project.test.content.intro", "Intro content.");
      const method = makeNote("method-id", "project.test.content.method", "Method content.");

      const notes: NotePropsByIdDict = { [root.id]: root, [intro.id]: intro, [method.id]: method };
      const profile: DocProfile = {
        rootNoteId: "root-id",
        rootNoteFname: "project.test.paper",
        exports: [{ format: "latex" }],
        meta: {},
        includes: [],
        discovered: ["project.test.content.intro", "project.test.content.method"],
        citations: [],
        assets: [],
      };

      const assembled = assembleDocument(profile, notes);
      const introIndex = assembled.body.indexOf("Intro content.");
      const methodIndex = assembled.body.indexOf("Method content.");
      expect(introIndex).toBeGreaterThan(-1);
      expect(methodIndex).toBeGreaterThan(-1);
      expect(introIndex).toBeLessThan(methodIndex);
    });

    it("should shift heading depths for embedded notes", () => {
      const root = makeNote("root-id", "project.test.paper", "# Title\n\n![[project.test.content.intro]]");
      const intro = makeNote("intro-id", "project.test.content.intro", "# Introduction\n\nIntro text.");

      const notes: NotePropsByIdDict = { [root.id]: root, [intro.id]: intro };
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

      const assembled = assembleDocument(profile, notes);
      expect(assembled.body).toContain("# Title");
      expect(assembled.body).toContain("## Introduction");
      expect(assembled.body).not.toMatch(/^# Introduction\n\nIntro text.$/m);
    });

    it("should handle unresolved refs gracefully", () => {
      const root = makeNote("root-id", "project.test.paper", "# Paper\n\n![[missing.note]]");
      const notes: NotePropsByIdDict = { [root.id]: root };
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

      const assembled = assembleDocument(profile, notes);
      expect(assembled.body).toContain("Unresolved reference");
      expect(assembled.unresolvedRefs).toContain("missing.note");
    });

    it("should prevent cyclic inclusion", () => {
      const root = makeNote("root-id", "project.test.paper", "# Paper\n\n![[project.test.a]]");
      const a = makeNote("a-id", "project.test.a", "# A\n\n![[project.test.b]]");
      const b = makeNote("b-id", "project.test.b", "# B\n\n![[project.test.a]]");

      const notes: NotePropsByIdDict = { [root.id]: root, [a.id]: a, [b.id]: b };
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

      const assembled = assembleDocument(profile, notes);
      expect(assembled.body).toContain("Note already included");
    });
  });
});
