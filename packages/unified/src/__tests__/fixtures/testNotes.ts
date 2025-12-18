/**
 * Test fixtures for creating mock NoteProps objects
 * Used across all unified module tests
 */

import {
  NoteProps,
  DVault,
  genDefaultDendronConfig,
  DendronConfig,
} from "@saili/common-all";

/**
 * Creates a default test vault
 */
export function createTestVault(overrides?: Partial<DVault>): DVault {
  return {
    fsPath: "/test/vault",
    ...overrides,
  };
}

/**
 * Creates a default test config
 */
export function createTestConfig(overrides?: Partial<DendronConfig>): DendronConfig {
  return {
    ...genDefaultDendronConfig(),
    ...overrides,
  };
}

/**
 * Creates a basic test note with minimal required fields
 */
export function createTestNote(
  overrides?: Partial<NoteProps>
): NoteProps {
  const vault = overrides?.vault ?? createTestVault();
  return {
    id: "test-note-id",
    fname: "test-note",
    title: "Test Note",
    desc: "A test note",
    created: Date.now(),
    updated: Date.now(),
    links: [],
    anchors: {},
    type: "note",
    parent: "",
    children: [],
    stub: false,
    custom: {},
    tags: [],
    traits: [],
    vault,
    data: {},
    body: "",
    ...overrides,
  };
}

/**
 * Creates a test note with markdown content
 */
export function createTestNoteWithBody(
  body: string,
  overrides?: Partial<NoteProps>
): NoteProps {
  return createTestNote({
    body,
    ...overrides,
  });
}

/**
 * Creates a test note with wiki links
 */
export function createTestNoteWithWikiLinks(
  links: string[],
  overrides?: Partial<NoteProps>
): NoteProps {
  const body = links.map((link) => `[[${link}]]`).join("\n");
  return createTestNoteWithBody(body, overrides);
}

/**
 * Creates a test note with hashtags
 */
export function createTestNoteWithHashtags(
  tags: string[],
  overrides?: Partial<NoteProps>
): NoteProps {
  const body = tags.map((tag) => `#${tag}`).join(" ");
  return createTestNoteWithBody(body, overrides);
}

/**
 * Creates a test note with frontmatter
 */
export function createTestNoteWithFrontmatter(
  frontmatter: Record<string, any>,
  body: string = "",
  overrides?: Partial<NoteProps>
): NoteProps {
  const yaml = Object.entries(frontmatter)
    .map(([key, value]) => `${key}: ${JSON.stringify(value)}`)
    .join("\n");
  const content = `---\n${yaml}\n---\n\n${body}`;
  return createTestNoteWithBody(content, overrides);
}
