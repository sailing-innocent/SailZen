/**
 * Tests for sailzenCite remark plugin
 */

import {
  sailzenCite,
  CITE_REGEX,
} from "../sailzenCite";
import { createTestNoteWithBody } from "../../__tests__/fixtures/testNotes";
import { processNoteFull } from "../../__tests__/utils/testHelpers";
import { DendronASTTypes } from "../../types";

describe("sailzenCite plugin", () => {
  describe("CITE_REGEX", () => {
    test("should match basic cite directive", () => {
      const match = CITE_REGEX.exec("::cite[foo]");
      expect(match).not.toBeNull();
      expect(match?.[1]).toBe("foo");
    });

    test("should match cite with multiple keys", () => {
      const match = CITE_REGEX.exec("::cite[foo, bar]");
      expect(match).not.toBeNull();
      expect(match?.[1]).toBe("foo, bar");
    });

    test("should match cite with spaces", () => {
      const match = CITE_REGEX.exec("::cite[ foo , bar ]");
      expect(match).not.toBeNull();
      expect(match?.[1]).toBe(" foo , bar ");
    });

    test("should not match incomplete cite", () => {
      const match = CITE_REGEX.exec("::cite[foo");
      expect(match).toBeNull();
    });

    test("should not match plain text", () => {
      const match = CITE_REGEX.exec("regular text");
      expect(match).toBeNull();
    });

    test("should not match cite in middle of text", () => {
      const match = CITE_REGEX.exec("text ::cite[foo]");
      expect(match).toBeNull();
    });
  });

  // NOTE: Plugin integration tests are skipped because the tokenizer
  // requires a full MDUtilsV5 processor context with config.
  describe.skip("sailzenCite plugin integration", () => {
    test("should parse cite directive", () => {
      // Skipped: requires full processor context
    });

    test("should parse multiple cites", () => {
      // Skipped: requires full processor context
    });
  });

  describe("sailzenCite with full processor", () => {
    test("should render cite in HTML", async () => {
      const note = createTestNoteWithBody("See ::cite[foo, bar] for details.");
      const html = await processNoteFull(note);
      expect(html).toContain("foo");
      expect(html).toContain("bar");
    });

    test("should render single key cite", async () => {
      const note = createTestNoteWithBody("Reference: ::cite[key1]");
      const html = await processNoteFull(note);
      expect(html).toContain("key1");
    });
  });
});
