/**
 * Tests for sailzenFigure remark plugin
 */

import {
  sailzenFigure,
  FIGURE_REGEX,
} from "../sailzenFigure";
import { createTestNoteWithBody } from "../../__tests__/fixtures/testNotes";
import { processNoteFull } from "../../__tests__/utils/testHelpers";
import { DendronASTTypes } from "../../types";

describe("sailzenFigure plugin", () => {
  describe("FIGURE_REGEX", () => {
    test("should match basic figure directive", () => {
      const match = FIGURE_REGEX.exec("::figure[Caption](image.png)");
      expect(match).not.toBeNull();
      expect(match?.[1]).toBe("Caption");
      expect(match?.[2]).toBe("image.png");
    });

    test("should match figure with options", () => {
      const match = FIGURE_REGEX.exec(
        '::figure[Overview](fig_teaser){width="\\linewidth"}'
      );
      expect(match).not.toBeNull();
      expect(match?.[1]).toBe("Overview");
      expect(match?.[2]).toBe("fig_teaser");
      expect(match?.[3]).toBe('width="\\linewidth"');
    });

    test("should match figure with empty caption", () => {
      const match = FIGURE_REGEX.exec("::figure[](empty.png)");
      expect(match).not.toBeNull();
      expect(match?.[1]).toBe("");
      expect(match?.[2]).toBe("empty.png");
    });

    test("should not match incomplete figure", () => {
      const match = FIGURE_REGEX.exec("::figure[Caption");
      expect(match).toBeNull();
    });

    test("should not match plain text", () => {
      const match = FIGURE_REGEX.exec("regular text");
      expect(match).toBeNull();
    });

    test("should not match figure in middle of text", () => {
      const match = FIGURE_REGEX.exec("text ::figure[Caption](img.png)");
      expect(match).toBeNull();
    });
  });

  // NOTE: Plugin integration tests are skipped because the tokenizer
  // requires a full MDUtilsV5 processor context with config.
  describe.skip("sailzenFigure plugin integration", () => {
    test("should parse figure directive", () => {
      // Skipped: requires full processor context
    });

    test("should parse figure with options", () => {
      // Skipped: requires full processor context
    });
  });

  describe("sailzenFigure with full processor", () => {
    test("should render figure in HTML", async () => {
      const note = createTestNoteWithBody(
        "::figure[Our method overview](method.png)"
      );
      const html = await processNoteFull(note);
      expect(html).toContain("method.png");
      expect(html).toContain("Our method overview");
    });

    test("should render figure with options in HTML", async () => {
      const note = createTestNoteWithBody(
        '::figure[Results](results.png){width="100%"}'
      );
      const html = await processNoteFull(note);
      expect(html).toContain("results.png");
    });
  });
});
