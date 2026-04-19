import { remark } from "remark";
import remarkParse from "remark-parse";
import { DendronASTDest } from "../../types";
import { sailzenFigure } from "../sailzenFigure";
import { MDUtilsV5 } from "../..";

describe("sailzenFigure", () => {
  test("should parse ::figure[caption](src) into a figure node", () => {
    const processor = remark().use(remarkParse).use(sailzenFigure);
    const tree = processor.parse("::figure[Overview](fig_overview)");

    const root = tree as any;
    expect(root.children).toBeDefined();
    expect(root.children.length).toBe(1);

    const paragraph = root.children[0];
    expect(paragraph.type).toBe("paragraph");
    expect(paragraph.children.length).toBe(1);

    const figNode = paragraph.children[0];
    expect(figNode.type).toBe("sailzenFigure");
    expect(figNode.caption).toBe("Overview");
    expect(figNode.src).toBe("fig_overview");
    expect(figNode.options).toBeDefined();
  });

  test("should parse ::figure with options", () => {
    const processor = remark().use(remarkParse).use(sailzenFigure);
    const tree = processor.parse(
      "::figure[Overview](fig_overview){width=0.8\\textwidth}"
    );

    const root = tree as any;
    const figNode = root.children[0].children[0];
    expect(figNode.type).toBe("sailzenFigure");
    expect(figNode.caption).toBe("Overview");
    expect(figNode.src).toBe("fig_overview");
    expect(figNode.options).toBeDefined();
    expect(figNode.options.width).toBe("0.8\\textwidth");
  });

  test("should round-trip figure directive through stringify", () => {
    const processor = remark().use(remarkParse).use(sailzenFigure);

    const result = processor
      .processSync("::figure[Overview](fig_overview)")
      .toString();
    expect(result).toContain("::figure[Overview](fig_overview)");
  });

  test("should compile figure node to placeholder for DOC_EXPORT", () => {
    const processor = remark().use(remarkParse).use(sailzenFigure);

    MDUtilsV5.setProcData(processor as any, {
      dest: DendronASTDest.DOC_EXPORT,
    });

    const result = processor
      .processSync("::figure[Overview](fig_overview)")
      .toString();
    expect(result).toContain("__FIGURE__[fig_overview|Overview]");
  });
});
