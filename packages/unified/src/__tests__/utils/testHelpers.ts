/**
 * Test helper utilities for unified module tests
 */

import { remark } from "remark";
import remarkParse from "remark-parse";
import { Processor } from "unified";
import { NoteProps, DendronASTDest } from "@saili/common-all";
import { MDUtilsV5, ProcFlavor } from "../../utilsv5";
import { ProcDataFullOptsV5 } from "../../utilsv5";
import { createTestConfig } from "../fixtures/testNotes";

/**
 * Creates a basic remark processor for testing
 */
export function createTestProcessor(): Processor<any, any, any, any> {
  return remark().use(remarkParse) as any;
}

/**
 * Processes markdown content and returns the AST
 */
export async function processMarkdownToAST(markdown: string): Promise<any> {
  const processor = createTestProcessor();
  const result = await processor.process(markdown);
  return result.result;
}

/**
 * Processes markdown content and returns the string output
 */
export async function processMarkdownToString(markdown: string): Promise<string> {
  const processor = createTestProcessor();
  const result = await processor.process(markdown);
  return result.toString();
}

/**
 * Creates a full processor with all Dendron plugins for testing
 */
export function createFullTestProcessor(
  note: NoteProps,
  flavor: ProcFlavor = ProcFlavor.REGULAR
): Processor<any, any, any, any> {
  const config = createTestConfig();
  const data: ProcDataFullOptsV5 = {
    noteToRender: note,
    fname: note.fname,
    vault: note.vault,
    config,
    dest: DendronASTDest.HTML,
  };

  return MDUtilsV5.procRehypeFull(data, { flavor });
}

/**
 * Processes a note with full Dendron processor
 */
export async function processNoteFull(
  note: NoteProps,
  flavor: ProcFlavor = ProcFlavor.REGULAR
): Promise<string> {
  const processor = createFullTestProcessor(note, flavor);
  const result = await processor.process(note.body);
  return result.toString();
}

/**
 * Asserts that a string contains specific content
 */
export function expectContains(actual: string, expected: string): void {
  expect(actual).toContain(expected);
}

/**
 * Asserts that a string does not contain specific content
 */
export function expectNotContains(actual: string, unexpected: string): void {
  expect(actual).not.toContain(unexpected);
}

/**
 * Asserts that a regex matches a string
 */
export function expectMatches(actual: string, pattern: RegExp): void {
  expect(actual).toMatch(pattern);
}

/**
 * Asserts that a regex does not match a string
 */
export function expectNotMatches(actual: string, pattern: RegExp): void {
  expect(actual).not.toMatch(pattern);
}

/**
 * Waits for a specified number of milliseconds
 */
export function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
