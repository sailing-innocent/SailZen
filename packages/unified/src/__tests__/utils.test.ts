/**
 * Tests for utils.ts utility functions
 */

import { MdastUtils, renderFromNote } from "../utils";
import { createTestNote } from "./fixtures/testNotes";
import { getSlugger } from "@saili/common-all";
import { paragraph, root, text, heading } from "mdast-builder";

describe("MdastUtils", () => {
  describe("genMDMsg", () => {
    test("should generate a message AST", () => {
      const msg = "Test message";
      const ast = MdastUtils.genMDMsg(msg);

      expect(ast.type).toBe("root");
      expect(ast.children).toBeDefined();
      expect(ast.children.length).toBeGreaterThan(0);
    });
  });

  describe("genMDErrorMsg", () => {
    test("should generate an error message AST", () => {
      const msg = "Error message";
      const ast = MdastUtils.genMDErrorMsg(msg);

      expect(ast.type).toBe("root");
      expect(ast.children).toBeDefined();
    });
  });

  describe("findIndex", () => {
    test("should find index of matching element", () => {
      const array = [1, 2, 3, 4, 5];
      const index = MdastUtils.findIndex(array, (item) => item === 3);
      expect(index).toBe(2);
    });

    test("should return -1 if element not found", () => {
      const array = [1, 2, 3, 4, 5];
      const index = MdastUtils.findIndex(array, (item) => item === 10);
      expect(index).toBe(-1);
    });

    test("should find first matching element", () => {
      const array = [1, 2, 2, 3, 2];
      const index = MdastUtils.findIndex(array, (item) => item === 2);
      expect(index).toBe(1);
    });
  });

  describe("findHeader", () => {
    test("should find first header by slug", () => {
      const slugger = getSlugger();
      const nodes = [
        heading(1, [text("First Header")]),
        heading(2, [text("Second Header")]),
        paragraph([text("Content")]),
      ];

      // findHeader matches by slug, not exact text
      const result = MdastUtils.findHeader({
        nodes: nodes as any,
        match: "first-header",
        slugger,
      });

      expect(result).not.toBeNull();
      expect(result?.index).toBe(0);
      expect(result?.type).toBe("header");
    });

    test("should find header by slug", () => {
      const slugger = getSlugger();
      const nodes = [
        heading(1, [text("Test Header")]),
        paragraph([text("Content")]),
      ];

      const result = MdastUtils.findHeader({
        nodes: nodes as any,
        match: "test-header",
        slugger,
      });

      expect(result).not.toBeNull();
      expect(result?.index).toBe(0);
    });

    test("should return null if header not found", () => {
      const slugger = getSlugger();
      const nodes = [
        heading(1, [text("First Header")]),
        paragraph([text("Content")]),
      ];

      const result = MdastUtils.findHeader({
        nodes: nodes as any,
        match: "Non-existent Header",
        slugger,
      });

      expect(result).toBeNull();
    });
  });

  describe("renderFromNote", () => {
    test("should render note body", () => {
      const note = createTestNote({ body: "Test content" });
      const result = renderFromNote({ note });
      expect(result).toBe("Test content");
    });

    test("should return empty string for note without body", () => {
      const note = createTestNote({ body: "" });
      const result = renderFromNote({ note });
      expect(result).toBe("");
    });
  });
});
