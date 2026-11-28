/**
 * Tests for the pageElements remark plugin, registry and rendering helpers.
 */

import { SailASTDest, ProcFlavor } from "@saili/common-all";
import { MDUtilsV5 } from "../../utilsv5";
import {
  createTestConfig,
  createTestNoteWithBody,
  createTestVault,
} from "../../__tests__/fixtures/testNotes";
import { processNoteFull } from "../../__tests__/utils/testHelpers";
import {
  parseSailElem,
} from "../pageElements/remarkPageElements";
import {
  PageElementRegistry,
  getDefaultPageElementRegistry,
  resetDefaultPageElementRegistry,
  PAGE_ELEMENT_PREFIX_KEY,
  PAGE_ELEMENT_POSTFIX_KEY,
  PAGE_ELEMENT_HELP_KEY,
} from "../pageElements/registry";
import { NotePageElementProvider } from "../pageElements/types";

const baseRenderCtx = {
  note: createTestNoteWithBody(""),
  fname: "test",
  vault: createTestVault(),
  vaults: [createTestVault()],
  wsRoot: "/test",
  config: createTestConfig(),
  args: { _: [] },
  raw: '<sail-elem key="PREFIX" />',
  flavor: ProcFlavor.PREVIEW,
};

function renderNoteBody(body: string, config = createTestConfig()) {
  const note = createTestNoteWithBody(body);
  const proc = MDUtilsV5.procRehypeFull(
    {
      noteToRender: note,
      fname: note.fname,
      vault: note.vault,
      config,
      dest: SailASTDest.HTML,
    },
    { flavor: ProcFlavor.PREVIEW }
  );
  return proc.process(body).then((r: any) => r.toString());
}

beforeEach(() => {
  resetDefaultPageElementRegistry();
});

describe("parseSailElem", () => {
  test("parses self-closing marker", () => {
    const parsed = parseSailElem('<sail-elem key="PREFIX" />');
    expect(parsed).toBeDefined();
    expect(parsed?.key).toBe("PREFIX");
    expect(parsed?.args).toEqual({ _: [] });
    expect(parsed?.fallback).toBeUndefined();
  });

  test("parses marker with attributes as args", () => {
    const parsed = parseSailElem(
      '<sail-elem key="WEATHER" city="hangzhou" day="0" />'
    );
    expect(parsed?.key).toBe("WEATHER");
    expect(parsed?.args).toEqual({ _: [], city: "hangzhou", day: "0" });
  });

  test("parses single-quoted and unquoted attribute values", () => {
    const parsed = parseSailElem(
      "<sail-elem key='WEATHER' city=hangzhou />"
    );
    expect(parsed?.key).toBe("WEATHER");
    expect(parsed?.args).toEqual({ _: [], city: "hangzhou" });
  });

  test("boolean attribute becomes 'true'", () => {
    const parsed = parseSailElem('<sail-elem key="FOO" detailed />');
    expect(parsed?.args).toEqual({ _: [], detailed: "true" });
  });

  test("parses paired marker with fallback content", () => {
    const parsed = parseSailElem(
      '<sail-elem key="WEATHER">loading weather…</sail-elem>'
    );
    expect(parsed?.key).toBe("WEATHER");
    expect(parsed?.fallback).toBe("loading weather…");
  });

  test("paired marker may span multiple lines", () => {
    const raw = '<sail-elem key="WEATHER">\nfallback **text**\n</sail-elem>';
    const parsed = parseSailElem(raw);
    expect(parsed?.key).toBe("WEATHER");
    expect(parsed?.fallback).toContain("fallback **text**");
    expect(parsed?.raw).toBe(raw);
  });

  test("rejects missing key attribute", () => {
    expect(parseSailElem("<sail-elem />")).toBeUndefined();
    expect(parseSailElem('<sail-elem city="hangzhou" />')).toBeUndefined();
  });

  test("rejects non-marker html", () => {
    expect(parseSailElem("<div>hello</div>")).toBeUndefined();
    expect(parseSailElem('<sail-elem key="PREFIX">unclosed')).toBeUndefined();
    expect(parseSailElem("</sail-elem>")).toBeUndefined();
  });

  test("rejects marker embedded in other content", () => {
    expect(
      parseSailElem('<sail-elem key="PREFIX" /> trailing')
    ).toBeUndefined();
  });
});

describe("PageElementRegistry", () => {
  const makeProvider = (
    key: string,
    html = `<p>${key} content</p>`
  ): NotePageElementProvider => ({
    key,
    title: `${key} title`,
    description: `${key} description`,
    render: () => html,
  });

  test("default registry has built-in providers", () => {
    const registry = getDefaultPageElementRegistry();
    expect(registry.has(PAGE_ELEMENT_PREFIX_KEY)).toBe(true);
    expect(registry.has(PAGE_ELEMENT_POSTFIX_KEY)).toBe(true);
    expect(registry.has(PAGE_ELEMENT_HELP_KEY)).toBe(true);
  });

  test("register and get", () => {
    const registry = new PageElementRegistry();
    registry.register(makeProvider("WEATHER"));
    expect(registry.has("WEATHER")).toBe(true);
    expect(registry.get("WEATHER")?.title).toBe("WEATHER title");
  });

  test("duplicate register throws, override works", () => {
    const registry = new PageElementRegistry();
    registry.register(makeProvider("WEATHER"));
    expect(() => registry.register(makeProvider("WEATHER"))).toThrow();
    registry.register(makeProvider("WEATHER", "<p>v2</p>"), {
      override: true,
    });
    expect(registry.get("WEATHER")).toBeDefined();
  });

  test("invalid key throws", () => {
    const registry = new PageElementRegistry();
    expect(() => registry.register(makeProvider("weather"))).toThrow();
  });

  test("unregister removes provider", () => {
    const registry = new PageElementRegistry();
    registry.register(makeProvider("WEATHER"));
    expect(registry.unregister("WEATHER")).toBe(true);
    expect(registry.has("WEATHER")).toBe(false);
  });

  test("render returns provider html", async () => {
    const registry = new PageElementRegistry();
    registry.register(makeProvider("WEATHER", "<p>sunny</p>"));
    const html = await registry.render("WEATHER", baseRenderCtx);
    expect(html).toBe("<p>sunny</p>");
  });

  test("render unknown key degrades to help instead of throwing", async () => {
    const registry = new PageElementRegistry();
    const html = await registry.render("MISSING", baseRenderCtx);
    expect(html).toContain("sail-page-element-help");
  });

  test("provider errors become a non-fatal error box", async () => {
    const registry = new PageElementRegistry();
    registry.register({
      key: "BROKEN",
      title: "Broken",
      description: "always throws",
      render: () => {
        throw new Error("boom");
      },
    });
    const html = await registry.render("BROKEN", baseRenderCtx);
    expect(html).toContain("sail-page-element-error");
    expect(html).toContain("boom");
  });

  test("cacheTtlMs caches output per note+args", async () => {
    const registry = new PageElementRegistry();
    let calls = 0;
    registry.register({
      key: "COUNTER",
      title: "Counter",
      description: "counts renders",
      cacheTtlMs: 60_000,
      render: () => {
        calls += 1;
        return `<p>${calls}</p>`;
      },
    });
    const first = await registry.render("COUNTER", baseRenderCtx);
    const second = await registry.render("COUNTER", baseRenderCtx);
    expect(first).toBe("<p>1</p>");
    expect(second).toBe("<p>1</p>");
    expect(calls).toBe(1);
    registry.clearCache();
    const third = await registry.render("COUNTER", baseRenderCtx);
    expect(third).toBe("<p>2</p>");
  });
});

describe("pageElements plugin (full HTML pipeline)", () => {
  test("renders built-in PREFIX help into a page element div", async () => {
    const html = await renderNoteBody(
      '<sail-elem key="PREFIX" />\n\nSome content.'
    );
    expect(html).toContain("sail-page-element");
    expect(html).toContain("sail-page-element-prefix");
    expect(html).toContain('data-page-element="PREFIX"');
    expect(html).toContain("sail-page-element-help");
    expect(html).toContain("Some content.");
  });

  test("renders POSTFIX at the end of the note", async () => {
    const html = await renderNoteBody(
      'Some content.\n\n<sail-elem key="POSTFIX" />'
    );
    expect(html).toContain("sail-page-element-postfix");
    expect(html.indexOf("Some content.")).toBeLessThan(
      html.indexOf("sail-page-element-postfix")
    );
  });

  test("custom provider with attribute args renders live content", async () => {
    const registry = getDefaultPageElementRegistry();
    let seenArgs: any;
    registry.register({
      key: "WEATHER",
      title: "Weather",
      description: "weather forecast",
      usage: '<sail-elem key="WEATHER" city="hangzhou" />',
      render: (ctx) => {
        seenArgs = ctx.args;
        return `<span class="weather">sunny in ${ctx.args.city}</span>`;
      },
    });
    const html = await renderNoteBody(
      '<sail-elem key="WEATHER" city="hangzhou" />'
    );
    expect(html).toContain('class="weather"');
    expect(html).toContain("sunny in hangzhou");
    expect(seenArgs).toEqual({ _: [], city: "hangzhou" });
  });

  test("provider receives fallback content of paired markers", async () => {
    const registry = getDefaultPageElementRegistry();
    let seenFallback: string | undefined;
    registry.register({
      key: "WEATHER",
      title: "Weather",
      description: "weather forecast",
      render: (ctx) => {
        seenFallback = ctx.fallback;
        return `<span>live weather</span>`;
      },
    });
    // Paired markers must put the open tag on its own line (standard
    // CommonMark raw-html-block rule), otherwise the tag is inline html.
    const html = await renderNoteBody(
      '<sail-elem key="WEATHER">\n天气加载中…\n</sail-elem>'
    );
    expect(seenFallback).toContain("天气加载中…");
    expect(html).toContain("live weather");
  });

  test("unregistered marker passes through as raw html (generic fallback)", async () => {
    const html = await renderNoteBody(
      '<sail-elem key="NOT_A_THING" />\n\nSome content.'
    );
    // untouched: no page element wrapper, raw tag preserved for other
    // renderers. Note: rehype-raw normalizes the self-closing unknown tag
    // into an open tag, exactly like a browser/generic renderer would.
    expect(html).not.toContain("sail-page-element");
    expect(html).toContain('<sail-elem key="NOT_A_THING">');
    expect(html).toContain("Some content.");
  });

  test("marker embedded in a paragraph is not transformed", async () => {
    const html = await renderNoteBody(
      'Please see <sail-elem key="PREFIX" /> for details.'
    );
    expect(html).not.toContain("sail-page-element-help");
  });

  test("provider errors do not break the note render", async () => {
    const registry = getDefaultPageElementRegistry();
    registry.register({
      key: "BROKEN",
      title: "Broken",
      description: "always throws",
      render: () => {
        throw new Error("query failed");
      },
    });
    const html = await renderNoteBody('<sail-elem key="BROKEN" />\n\nAfter.');
    expect(html).toContain("sail-page-element-error");
    expect(html).toContain("query failed");
    expect(html).toContain("After.");
  });

  test("async providers are awaited", async () => {
    const registry = getDefaultPageElementRegistry();
    registry.register({
      key: "ASYNC_THING",
      title: "Async",
      description: "async provider",
      render: async () => {
        await new Promise((resolve) => setTimeout(resolve, 10));
        return `<em>async result</em>`;
      },
    });
    const html = await renderNoteBody('<sail-elem key="ASYNC_THING" />');
    expect(html).toContain("<em>async result</em>");
  });

  test("latex math is completely unaffected (katex enabled)", async () => {
    // $$...$$ was the old marker syntax; it must now be treated purely as math.
    const html = await renderNoteBody("$$E=mc^2$$");
    expect(html).not.toContain("sail-page-element");
    expect(html.toLowerCase()).toContain("katex");
  });

  test("help output escapes example markers", async () => {
    const html = await renderNoteBody('<sail-elem key="HELP" />');
    expect(html).toContain("sail-page-element-help");
    // example usages must be escaped so they show as text, not real
    // elements (the `<` is serialized as a character reference)
    expect(html).toContain('sail-elem key="HELP" />');
    expect(html).not.toContain('<sail-elem key="HELP" />');
  });
});

describe("pageElements plugin (markdown round-trip)", () => {
  test("marker survives parse -> stringify for MD_SAIL dest", async () => {
    const body =
      '<sail-elem key="PREFIX" />\n\nSome content with [[links.other]].\n\n<sail-elem key="POSTFIX" />';
    const note = createTestNoteWithBody(body);
    const proc = MDUtilsV5.procRemarkFull(
      {
        noteToRender: note,
        fname: note.fname,
        vault: note.vault,
        config: createTestConfig(),
        dest: SailASTDest.MD_SAIL,
      },
      { flavor: ProcFlavor.REGULAR }
    );
    const out = (await proc.process(body)).toString();
    expect(out).toContain('<sail-elem key="PREFIX" />');
    expect(out).toContain('<sail-elem key="POSTFIX" />');
    expect(out).toContain("Some content");
  });

  test("paired marker with fallback survives round-trip", async () => {
    const registry = getDefaultPageElementRegistry();
    registry.register({
      key: "WEATHER",
      title: "Weather",
      description: "weather forecast",
      render: () => "<p>x</p>",
    });
    const body = '<sail-elem key="WEATHER" city="hangzhou">fallback</sail-elem>';
    const note = createTestNoteWithBody(body);
    const proc = MDUtilsV5.procRemarkFull(
      {
        noteToRender: note,
        fname: note.fname,
        vault: note.vault,
        config: createTestConfig(),
        dest: SailASTDest.MD_SAIL,
      },
      { flavor: ProcFlavor.REGULAR }
    );
    const out = (await proc.process(body)).toString();
    expect(out).toContain(body);
  });
});
