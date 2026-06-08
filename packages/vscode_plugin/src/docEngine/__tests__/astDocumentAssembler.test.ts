/**
 * @file astDocumentAssembler.test.ts
 * @brief Unit tests for AST-based document assembly
 */

import { NoteProps, NotePropsByIdDict, DocProfile } from "@saili/common-all";
import { assembleDocumentAST, astToAssembledDocument, NoteParser } from "../astDocumentAssembler";

/** Minimal markdown parser for tests — avoids ESM-only remark dependency */
function createMockParser(): NoteParser {
  return (body: string) => {
    const lines = body.split("\n");
    const children: any[] = [];
    let currentParagraph: any[] = [];

    const flushParagraph = () => {
      if (currentParagraph.length > 0) {
        children.push({
          type: "paragraph",
          children: currentParagraph,
        });
        currentParagraph = [];
      }
    };

    const pushText = (text: string) => {
      currentParagraph.push({ type: "text", value: text });
    };

    for (const line of lines) {
      const headingMatch = line.match(/^(#{1,6})\s+(.+)$/);
      if (headingMatch) {
        flushParagraph();
        children.push({
          type: "heading",
          depth: headingMatch[1].length,
          children: [{ type: "text", value: headingMatch[2] }],
        });
      } else if (line.trim() === "") {
        flushParagraph();
      } else {
        // Check for note ref syntax: ![[fname]] or ![[fname#anchor]]
        const refRegex = /!?\[\[([^\]]+)\]\]/g;
        let lastIndex = 0;
        let match: RegExpExecArray | null;
        let hasRef = false;
        while ((match = refRegex.exec(line)) !== null) {
          hasRef = true;
          if (match.index > lastIndex) {
            pushText(line.slice(lastIndex, match.index));
          }
          const refContent = match[1];
          const [fname, anchor] = refContent.split("#");
          currentParagraph.push({
            type: "refLinkV2",
            data: {
              link: {
                from: { fname },
                data: { anchorStart: anchor || undefined },
              },
            },
          });
          lastIndex = match.index + match[0].length;
        }
        if (hasRef && lastIndex < line.length) {
          pushText(line.slice(lastIndex));
        }
        if (!hasRef) {
          pushText(line);
        }
      }
    }
    flushParagraph();

    return { type: "root", children } as any;
  };
}

/** Minimal AST-to-markdown serializer for tests */
function createMockSerializer(): (ast: any) => string {
  return (ast: any) => {
    const serializeNode = (node: any): string => {
      if (node.type === "root") {
        return node.children.map(serializeNode).join("\n\n");
      }
      if (node.type === "paragraph") {
        return node.children.map(serializeNode).join("");
      }
      if (node.type === "heading") {
        return "#".repeat(node.depth) + " " + node.children.map(serializeNode).join("");
      }
      if (node.type === "text") {
        return node.value;
      }
      if (node.type === "refLinkV2") {
        const fname = node.data?.link?.from?.fname || "";
        const anchor = node.data?.link?.data?.anchorStart;
        return anchor ? `![[${fname}#${anchor}]]` : `![[${fname}]]`;
      }
      return "";
    };
    return serializeNode(ast);
  };
}

describe("astDocumentAssembler", () => {
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

  const mockParser = createMockParser();
  const mockSerializer = createMockSerializer();

  describe("assembleDocumentAST", () => {
    it("should parse root note into AST", () => {
      const root = makeNote("root-id", "project.test.paper", "# Paper\n\nHello.");
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

      const result = assembleDocumentAST(profile, notes, mockParser);
      expect(result.ast.type).toBe("root");
      expect(result.includedNotes).toContain("root-id");
    });

    it("should expand note refs recursively", () => {
      const root = makeNote("root-id", "project.test.paper", "# Paper\n\n![[project.test.intro]]");
      const intro = makeNote("intro-id", "project.test.intro", "## Introduction\n\nIntro text.");
      const notes: NotePropsByIdDict = {
        [root.id]: root,
        [intro.id]: intro,
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

      const result = assembleDocumentAST(profile, notes, mockParser);
      expect(result.includedNotes).toContain("intro-id");
      // The intro note's heading should be shifted from depth 2 to depth 3
      const allHeadings: any[] = [];
      const collectHeadings = (node: any) => {
        if (node.type === "heading") allHeadings.push(node);
        if (node.children) node.children.forEach(collectHeadings);
      };
      collectHeadings(result.ast);
      const introHeading = allHeadings.find((n: any) =>
        n.children?.some((c: any) => c.value === "Introduction")
      ) as any;
      expect(introHeading).toBeDefined();
      expect(introHeading!.depth).toBe(3);
    });

    it("should report unresolved refs", () => {
      const root = makeNote("root-id", "project.test.paper", "# Paper\n\n![[missing]]");
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

      const result = assembleDocumentAST(profile, notes, mockParser);
      expect(result.unresolvedRefs).toContain("missing");
    });
  });

  describe("astToAssembledDocument", () => {
    it("should produce a valid assembled document", () => {
      const root = makeNote("root-id", "project.test.paper", "# Paper\n\nHello world.");
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

      const astResult = assembleDocumentAST(profile, notes, mockParser);
      const assembled = astToAssembledDocument(astResult, mockSerializer);
      expect(assembled.body).toContain("Hello world.");
      expect(assembled.includedNotes).toContain("root-id");
    });
  });
});
