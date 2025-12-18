/**
 * Tests for utilsWeb.ts
 */

import { MDUtilsV5Web } from "../utilsWeb";
import { createTestNote, createTestNoteWithBody, createTestConfig, createTestVault } from "./fixtures/testNotes";
import { ProcFlavor } from "@saili/common-all";

describe("MDUtilsV5Web", () => {
  describe("procRehypeWeb", () => {
    test("should create a processor", () => {
      const note = createTestNoteWithBody("# Test\n\nContent");
      const config = createTestConfig();
      const vault = createTestVault();

      const processor = MDUtilsV5Web.procRehypeWeb({
        noteToRender: note,
        fname: note.fname,
        vault,
        config,
      });

      expect(processor).toBeDefined();
    });

    test("should process markdown to HTML", async () => {
      const note = createTestNoteWithBody("# Test\n\nContent");
      const config = createTestConfig();
      const vault = createTestVault();

      const processor = MDUtilsV5Web.procRehypeWeb({
        noteToRender: note,
        fname: note.fname,
        vault,
        config,
      });

      const result = await processor.process(note.body);
      const html = result.toString();

      expect(html).toBeDefined();
      expect(typeof html).toBe("string");
      expect(html.length).toBeGreaterThan(0);
    });

    test("should handle wiki links", async () => {
      const note = createTestNoteWithBody("[[test-link]]");
      const config = createTestConfig();
      const vault = createTestVault();

      const processor = MDUtilsV5Web.procRehypeWeb({
        noteToRender: note,
        fname: note.fname,
        vault,
        config,
      });

      const result = await processor.process(note.body);
      const html = result.toString();

      expect(html).toBeDefined();
    });

    test("should handle hashtags", async () => {
      const note = createTestNoteWithBody("#important");
      const config = createTestConfig();
      const vault = createTestVault();

      const processor = MDUtilsV5Web.procRehypeWeb({
        noteToRender: note,
        fname: note.fname,
        vault,
        config,
      });

      const result = await processor.process(note.body);
      const html = result.toString();

      expect(html).toBeDefined();
    });

    test("should accept flavor option", () => {
      const note = createTestNoteWithBody("Content");
      const config = createTestConfig();
      const vault = createTestVault();

      const processor = MDUtilsV5Web.procRehypeWeb(
        {
          noteToRender: note,
          fname: note.fname,
          vault,
          config,
        },
        { flavor: ProcFlavor.PREVIEW }
      );

      expect(processor).toBeDefined();
    });
  });
});
