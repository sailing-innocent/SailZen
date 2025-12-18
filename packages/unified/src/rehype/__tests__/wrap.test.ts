/**
 * Tests for wrap rehype plugin
 */

import { remark } from "remark";
import remarkParse from "remark-parse";
import remarkRehype from "remark-rehype";
import rehypeStringify from "rehype-stringify";
import { wrap } from "../wrap";

describe("wrap rehype plugin", () => {
  test("should wrap elements matching selector", async () => {
    const processor = remark()
      .use(remarkParse)
      .use(remarkRehype)
      .use(wrap, {
        selector: "p",
        wrapper: "div",
      })
      .use(rehypeStringify);

    const result = await processor.process("Hello world");
    const html = result.toString();

    expect(html).toContain("<div>");
    expect(html).toContain("<p>");
    expect(html).toContain("Hello world");
  });

  test("should wrap headings", async () => {
    const processor = remark()
      .use(remarkParse)
      .use(remarkRehype)
      .use(wrap, {
        selector: "h1",
        wrapper: "section",
      })
      .use(rehypeStringify);

    const result = await processor.process("# Heading");
    const html = result.toString();

    expect(html).toContain("<section>");
    expect(html).toContain("<h1>");
    expect(html).toContain("Heading");
  });

  test("should wrap multiple matching elements", async () => {
    const processor = remark()
      .use(remarkParse)
      .use(remarkRehype)
      .use(wrap, {
        selector: "p",
        wrapper: "div",
      })
      .use(rehypeStringify);

    const result = await processor.process("First paragraph\n\nSecond paragraph");
    const html = result.toString();

    // Both paragraphs should be wrapped
    const divMatches = html.match(/<div>/g);
    expect(divMatches?.length).toBeGreaterThanOrEqual(2);
  });

  test("should handle complex wrapper selector", async () => {
    const processor = remark()
      .use(remarkParse)
      .use(remarkRehype)
      .use(wrap, {
        selector: "p",
        wrapper: "div.class-name",
      })
      .use(rehypeStringify);

    const result = await processor.process("Hello world");
    const html = result.toString();

    expect(html).toContain("class-name");
    expect(html).toContain("Hello world");
  });

  test("should not wrap non-matching elements", async () => {
    const processor = remark()
      .use(remarkParse)
      .use(remarkRehype)
      .use(wrap, {
        selector: "h1",
        wrapper: "div",
      })
      .use(rehypeStringify);

    const result = await processor.process("Regular paragraph");
    const html = result.toString();

    // Should not wrap paragraphs when selector is h1
    expect(html).not.toContain("<div><p>");
  });
});
