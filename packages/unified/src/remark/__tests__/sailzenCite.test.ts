import { remark } from "remark";
import remarkParse from "remark-parse";
import { DendronASTDest } from "../../types";
import { sailzenCite } from "../sailzenCite";
import { MDUtilsV5 } from "../..";

describe("sailzenCite", () => {
  test("should parse ::cite[key] into a cite node", () => {
    const processor = remark().use(remarkParse).use(sailzenCite);
    const tree = processor.parse("::cite[foo]");

    // The tree should have a root > paragraph > sailzenCite node
    const root = tree as any;
    expect(root.children).toBeDefined();
    expect(root.children.length).toBe(1);

    const paragraph = root.children[0];
    expect(paragraph.type).toBe("paragraph");
    expect(paragraph.children.length).toBe(1);

    const citeNode = paragraph.children[0];
    expect(citeNode.type).toBe("sailzenCite");
    expect(citeNode.keys).toEqual(["foo"]);
  });

  test("should parse ::cite with multiple keys", () => {
    const processor = remark().use(remarkParse).use(sailzenCite);
    const tree = processor.parse("::cite[foo, bar]");

    const root = tree as any;
    const citeNode = root.children[0].children[0];
    expect(citeNode.type).toBe("sailzenCite");
    expect(citeNode.keys).toEqual(["foo", "bar"]);
  });

  test("should round-trip ::cite[key] through stringify", () => {
    const processor = remark().use(remarkParse).use(sailzenCite);

    const result = processor.processSync("::cite[foo]").toString();
    expect(result).toContain("::cite[foo]");
  });

  test("should compile cite node to placeholder for DOC_EXPORT", () => {
    const processor = remark().use(remarkParse).use(sailzenCite);

    MDUtilsV5.setProcData(processor as any, {
      dest: DendronASTDest.DOC_EXPORT,
    });

    const result = processor.processSync("::cite[foo]").toString();
    expect(result).toContain("__CITE__[foo]");
  });
});
