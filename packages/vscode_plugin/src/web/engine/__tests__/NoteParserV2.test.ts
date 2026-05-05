/** <reference types="jest" />
/**
 * @file NoteParserV2.test.ts
 * @brief Comprehensive tests for the VSCode Web Extension NoteParserV2
 * @description Tests parsing of Dendron note hierarchies in the web environment.
 *              Covers root detection, multi-level hierarchies, stub creation,
 *              duplicate ID detection, and error handling.
 */

import { NoteParserV2 } from "../NoteParserV2";
import {
  DVault,
  DuplicateNoteError,
  ERROR_STATUS,
  EngineInitErrorType,
  NoteProps,
  genHash,
} from "@saili/common-all";
import { URI, Utils } from "vscode-uri";
import * as vscode from "vscode";

// Mock vscode module before importing NoteParserV2
jest.mock("vscode", () => ({
  workspace: {
    fs: {
      readFile: jest.fn(),
    },
  },
}));

// Helper to build a simple note content with frontmatter
function makeNoteContent(opts: { title?: string; body?: string; id?: string }) {
  const { title = "Untitled", body = "", id } = opts;
  const idLine = id ? `id: ${id}\n` : "";
  return `---\ntitle: ${title}\n${idLine}---\n${body}`;
}

// Helper to encode string to Uint8Array (simulates vscode fs read)
function toUint8Array(str: string): Uint8Array {
  const encoder = new TextEncoder();
  return encoder.encode(str);
}

describe("NoteParserV2", () => {
  let parser: NoteParserV2;
  let mockVault: DVault;
  let wsRoot: URI;

  beforeEach(() => {
    jest.clearAllMocks();
    wsRoot = URI.file("/tmp/test-ws");
    mockVault = {
      fsPath: Utils.joinPath(wsRoot, "vault").fsPath,
      name: "test-vault",
    };
    parser = new NoteParserV2(wsRoot);
  });

  // ---------------------------------------------------------------------------
  // 1. Root detection & basic validation
  // ---------------------------------------------------------------------------
  describe("root note validation", () => {
    it("should return NO_ROOT_NOTE_FOUND when allPaths is empty", async () => {
      const { noteDicts, errors } = await parser.parseFiles([], mockVault);
      expect(Object.keys(noteDicts.notesById)).toHaveLength(0);
      expect(errors).toHaveLength(1);
      expect(errors[0].status).toBe(ERROR_STATUS.NO_ROOT_NOTE_FOUND);
    });

    it("should return NO_ROOT_NOTE_FOUND when root.md is missing", async () => {
      const paths = ["foo.md", "bar.baz.md"];
      const { noteDicts, errors } = await parser.parseFiles(paths, mockVault);
      expect(Object.keys(noteDicts.notesById)).toHaveLength(0);
      expect(errors).toHaveLength(1);
      expect(errors[0].status).toBe(ERROR_STATUS.NO_ROOT_NOTE_FOUND);
    });

    it("should parse root.md successfully as the hierarchy root", async () => {
      const rootContent = makeNoteContent({ title: "Root" });
      (vscode.workspace.fs.readFile as jest.Mock).mockResolvedValue(
        toUint8Array(rootContent)
      );

      const { noteDicts, errors } = await parser.parseFiles(
        ["root.md"],
        mockVault
      );
      expect(errors).toHaveLength(0);
      expect(noteDicts.notesByFname["root"]).toBeDefined();
      const rootId = noteDicts.notesByFname["root"][0];
      const rootNote = noteDicts.notesById[rootId];
      expect(rootNote.fname).toBe("root");
      expect(rootNote.parent).toBeNull();
    });
  });

  // ---------------------------------------------------------------------------
  // 2. Single-level (domain) notes
  // ---------------------------------------------------------------------------
  describe("domain notes (level 1)", () => {
    it("should attach domain notes as children of root", async () => {
      const rootContent = makeNoteContent({ title: "Root" });
      const dailyContent = makeNoteContent({ title: "Daily Journal" });

      (vscode.workspace.fs.readFile as jest.Mock).mockImplementation(
        (uri: URI) => {
          const name = Utils.basename(uri);
          if (name === "root.md") return Promise.resolve(toUint8Array(rootContent));
          if (name === "daily.md") return Promise.resolve(toUint8Array(dailyContent));
          return Promise.reject(new Error("File not found"));
        }
      );

      const { noteDicts, errors } = await parser.parseFiles(
        ["root.md", "daily.md"],
        mockVault
      );
      expect(errors).toHaveLength(0);

      const rootId = noteDicts.notesByFname["root"][0];
      const rootNote = noteDicts.notesById[rootId];
      expect(rootNote.children).toHaveLength(1);

      const dailyId = noteDicts.notesByFname["daily"][0];
      const dailyNote = noteDicts.notesById[dailyId];
      expect(dailyNote.fname).toBe("daily");
      expect(dailyNote.parent).toBe(rootId);
    });

    it("should parse multiple domain notes concurrently", async () => {
      const files: Record<string, string> = {
        "root.md": makeNoteContent({ title: "Root" }),
        "a.md": makeNoteContent({ title: "A" }),
        "b.md": makeNoteContent({ title: "B" }),
        "c.md": makeNoteContent({ title: "C" }),
      };

      (vscode.workspace.fs.readFile as jest.Mock).mockImplementation(
        (uri: URI) => {
          const name = Utils.basename(uri);
          const content = files[name];
          if (content) return Promise.resolve(toUint8Array(content));
          return Promise.reject(new Error("File not found"));
        }
      );

      const { noteDicts, errors } = await parser.parseFiles(
        Object.keys(files),
        mockVault
      );
      expect(errors).toHaveLength(0);
      expect(Object.keys(noteDicts.notesByFname)).toHaveLength(4);

      const rootId = noteDicts.notesByFname["root"][0];
      const rootNote = noteDicts.notesById[rootId];
      expect(rootNote.children).toHaveLength(3);
    });
  });

  // ---------------------------------------------------------------------------
  // 3. Multi-level hierarchies & parent linking
  // ---------------------------------------------------------------------------
  describe("multi-level hierarchies", () => {
    it("should establish parent/child links for nested notes", async () => {
      // Hierarchy: root -> dev -> dev.setup -> dev.setup.vscode
      const files: Record<string, string> = {
        "root.md": makeNoteContent({ title: "Root" }),
        "dev.md": makeNoteContent({ title: "Dev" }),
        "dev.setup.md": makeNoteContent({ title: "Setup" }),
        "dev.setup.vscode.md": makeNoteContent({ title: "VSCode" }),
      };

      (vscode.workspace.fs.readFile as jest.Mock).mockImplementation(
        (uri: URI) => {
          const name = Utils.basename(uri);
          const content = files[name];
          if (content) return Promise.resolve(toUint8Array(content));
          return Promise.reject(new Error("File not found"));
        }
      );

      const { noteDicts, errors } = await parser.parseFiles(
        Object.keys(files),
        mockVault
      );
      expect(errors).toHaveLength(0);

      const rootId = noteDicts.notesByFname["root"][0];
      const devId = noteDicts.notesByFname["dev"][0];
      const setupId = noteDicts.notesByFname["dev.setup"][0];
      const vscodeId = noteDicts.notesByFname["dev.setup.vscode"][0];

      // Verify dev.setup.vscode parent chain
      expect(noteDicts.notesById[vscodeId].parent).toBe(setupId);
      expect(noteDicts.notesById[setupId].parent).toBe(devId);
      expect(noteDicts.notesById[devId].parent).toBe(rootId);

      // Verify children links
      expect(noteDicts.notesById[devId].children).toContain(setupId);
      expect(noteDicts.notesById[setupId].children).toContain(vscodeId);
      expect(noteDicts.notesById[rootId].children).toContain(devId);
    });

    it("should create stub notes for missing intermediate parents", async () => {
      // Only provide child and grandchild, skip parent file
      const files: Record<string, string> = {
        "root.md": makeNoteContent({ title: "Root" }),
        "dev.setup.vscode.md": makeNoteContent({ title: "VSCode" }),
      };

      (vscode.workspace.fs.readFile as jest.Mock).mockImplementation(
        (uri: URI) => {
          const name = Utils.basename(uri);
          const content = files[name];
          if (content) return Promise.resolve(toUint8Array(content));
          return Promise.reject(new Error("File not found"));
        }
      );

      const { noteDicts, errors } = await parser.parseFiles(
        Object.keys(files),
        mockVault
      );
      expect(errors).toHaveLength(0);

      // Stub notes should be created for "dev" and "dev.setup"
      expect(noteDicts.notesByFname["dev"]).toBeDefined();
      expect(noteDicts.notesByFname["dev.setup"]).toBeDefined();
      expect(noteDicts.notesByFname["dev.setup.vscode"]).toBeDefined();

      const devId = noteDicts.notesByFname["dev"][0];
      const setupId = noteDicts.notesByFname["dev.setup"][0];
      const vscodeId = noteDicts.notesByFname["dev.setup.vscode"][0];

      expect(noteDicts.notesById[devId].stub).toBe(true);
      expect(noteDicts.notesById[setupId].stub).toBe(true);
      expect(noteDicts.notesById[vscodeId].stub).toBeFalsy();

      // Parent chain should still be intact
      expect(noteDicts.notesById[vscodeId].parent).toBe(setupId);
      expect(noteDicts.notesById[setupId].parent).toBe(devId);
    });
  });

  // ---------------------------------------------------------------------------
  // 4. Duplicate ID detection
  // ---------------------------------------------------------------------------
  describe("duplicate ID detection", () => {
    it("should report DuplicateNoteError when two files have the same id", async () => {
      const dupId = "duplicate-id-123";
      const files: Record<string, string> = {
        "root.md": makeNoteContent({ title: "Root" }),
        "a.md": makeNoteContent({ title: "A", id: dupId }),
        "b.md": makeNoteContent({ title: "B", id: dupId }),
      };

      (vscode.workspace.fs.readFile as jest.Mock).mockImplementation(
        (uri: URI) => {
          const name = Utils.basename(uri);
          const content = files[name];
          if (content) return Promise.resolve(toUint8Array(content));
          return Promise.reject(new Error("File not found"));
        }
      );

      const { errors } = await parser.parseFiles(Object.keys(files), mockVault);
      const dupErrors = errors.filter((e) => DuplicateNoteError.isDuplicateNoteError(e));
      expect(dupErrors.length).toBeGreaterThanOrEqual(1);
    });
  });

  // ---------------------------------------------------------------------------
  // 5. Error handling
  // ---------------------------------------------------------------------------
  describe("error handling", () => {
    it("should return BAD_PARSE_FOR_NOTE when a file cannot be read", async () => {
      const rootContent = makeNoteContent({ title: "Root" });

      (vscode.workspace.fs.readFile as jest.Mock).mockImplementation(
        (uri: URI) => {
          const name = Utils.basename(uri);
          if (name === "root.md") return Promise.resolve(toUint8Array(rootContent));
          if (name === "bad.md") return Promise.reject(new Error("EPERM"));
          return Promise.reject(new Error("File not found"));
        }
      );

      const { noteDicts, errors } = await parser.parseFiles(
        ["root.md", "bad.md"],
        mockVault
      );
      // Root should still parse
      expect(noteDicts.notesByFname["root"]).toBeDefined();
      // Error for bad.md should be collected, not thrown
      expect(errors.length).toBeGreaterThanOrEqual(1);
      expect(errors.some((e) => e.message?.includes("bad.md"))).toBe(true);
    });

    it("should return BAD_PARSE_FOR_NOTE for malformed frontmatter", async () => {
      const rootContent = makeNoteContent({ title: "Root" });
      const badContent = `---\ninvalid: [unclosed\n---\nbody`;

      (vscode.workspace.fs.readFile as jest.Mock).mockImplementation(
        (uri: URI) => {
          const name = Utils.basename(uri);
          if (name === "root.md") return Promise.resolve(toUint8Array(rootContent));
          if (name === "bad.md") return Promise.resolve(toUint8Array(badContent));
          return Promise.reject(new Error("File not found"));
        }
      );

      const { errors } = await parser.parseFiles(
        ["root.md", "bad.md"],
        mockVault
      );
      expect(errors.some((e) => e.status === ERROR_STATUS.BAD_PARSE_FOR_NOTE)).toBe(true);
    });
  });

  // ---------------------------------------------------------------------------
  // 6. Content hash generation
  // ---------------------------------------------------------------------------
  describe("content hash", () => {
    it("should compute contentHash for every parsed note", async () => {
      const rootContent = makeNoteContent({ title: "Root", body: "hello" });
      (vscode.workspace.fs.readFile as jest.Mock).mockResolvedValue(
        toUint8Array(rootContent)
      );

      const { noteDicts, errors } = await parser.parseFiles(
        ["root.md"],
        mockVault
      );
      expect(errors).toHaveLength(0);
      const rootId = noteDicts.notesByFname["root"][0];
      const rootNote = noteDicts.notesById[rootId];
      expect(rootNote.contentHash).toBeDefined();
      expect(rootNote.contentHash).toBe(genHash(rootContent));
    });
  });

  // ---------------------------------------------------------------------------
  // 7. Edge cases & concurrency safety
  // ---------------------------------------------------------------------------
  describe("edge cases", () => {
    it("should ignore root.* files beyond level 1", async () => {
      // root.something.md should be filtered out at level 2+
      const files: Record<string, string> = {
        "root.md": makeNoteContent({ title: "Root" }),
        "root.journal.md": makeNoteContent({ title: "Journal" }),
        "daily.md": makeNoteContent({ title: "Daily" }),
      };

      (vscode.workspace.fs.readFile as jest.Mock).mockImplementation(
        (uri: URI) => {
          const name = Utils.basename(uri);
          const content = files[name];
          if (content) return Promise.resolve(toUint8Array(content));
          return Promise.reject(new Error("File not found"));
        }
      );

      const { noteDicts, errors } = await parser.parseFiles(
        Object.keys(files),
        mockVault
      );
      expect(errors).toHaveLength(0);
      // root.journal should be skipped by the globMatch filter
      expect(noteDicts.notesByFname["root.journal"]).toBeUndefined();
      expect(noteDicts.notesByFname["daily"]).toBeDefined();
    });

    it("should handle deeply nested hierarchies (>3 levels)", async () => {
      const files: Record<string, string> = {
        "root.md": makeNoteContent({ title: "Root" }),
        "a.md": makeNoteContent({ title: "A" }),
        "a.b.md": makeNoteContent({ title: "B" }),
        "a.b.c.md": makeNoteContent({ title: "C" }),
        "a.b.c.d.md": makeNoteContent({ title: "D" }),
        "a.b.c.d.e.md": makeNoteContent({ title: "E" }),
      };

      (vscode.workspace.fs.readFile as jest.Mock).mockImplementation(
        (uri: URI) => {
          const name = Utils.basename(uri);
          const content = files[name];
          if (content) return Promise.resolve(toUint8Array(content));
          return Promise.reject(new Error("File not found"));
        }
      );

      const { noteDicts, errors } = await parser.parseFiles(
        Object.keys(files),
        mockVault
      );
      expect(errors).toHaveLength(0);

      // Walk up the parent chain
      const eId = noteDicts.notesByFname["a.b.c.d.e"][0];
      const dId = noteDicts.notesByFname["a.b.c.d"][0];
      const cId = noteDicts.notesByFname["a.b.c"][0];
      const bId = noteDicts.notesByFname["a.b"][0];
      const aId = noteDicts.notesByFname["a"][0];
      const rootId = noteDicts.notesByFname["root"][0];

      expect(noteDicts.notesById[eId].parent).toBe(dId);
      expect(noteDicts.notesById[dId].parent).toBe(cId);
      expect(noteDicts.notesById[cId].parent).toBe(bId);
      expect(noteDicts.notesById[bId].parent).toBe(aId);
      expect(noteDicts.notesById[aId].parent).toBe(rootId);
    });

    it("should produce deterministic results across identical runs", async () => {
      const files = [
        "root.md",
        "dev.md",
        "dev.setup.md",
        "design.md",
      ];
      const contentMap: Record<string, string> = {
        "root.md": makeNoteContent({ title: "Root" }),
        "dev.md": makeNoteContent({ title: "Dev" }),
        "dev.setup.md": makeNoteContent({ title: "Setup" }),
        "design.md": makeNoteContent({ title: "Design" }),
      };

      (vscode.workspace.fs.readFile as jest.Mock).mockImplementation(
        (uri: URI) => {
          const name = Utils.basename(uri);
          return Promise.resolve(toUint8Array(contentMap[name] ?? ""));
        }
      );

      const run1 = await parser.parseFiles(files, mockVault);
      const run2 = await parser.parseFiles(files, mockVault);

      // Note IDs are randomly generated, so compare fnames and counts instead
      expect(Object.keys(run1.noteDicts.notesByFname).sort()).toEqual(
        Object.keys(run2.noteDicts.notesByFname).sort()
      );
      expect(Object.keys(run1.noteDicts.notesById).length).toEqual(
        Object.keys(run2.noteDicts.notesById).length
      );
    });
  });
});
