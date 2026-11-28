import * as fs from "fs";
import * as os from "os";
import * as path from "path";
import {
  extractHeadings,
  extractHeadingSection,
  extractWikilinks,
  findHeadingLine,
  NoteRecord,
  parseWikilinkInner,
  serializeNewNote,
  slugifyHeading,
} from "../src/core/vault/noteModel";
import { VaultIndex } from "../src/core/vault/vaultIndex";
import {
  buildWikilinkHref,
  extendMarkdownItWithSailZen,
  MarkdownItBlockStateLike,
  MarkdownItInlineStateLike,
  MarkdownItLike,
  MarkdownItTokenLike,
} from "../src/features/editor/markdownPreview";

function makeTempDir(prefix: string): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

/** Lightweight structural markdown-it test harness (zero external dependency). */
function createMiniMarkdownIt(): MarkdownItLike {
  const blockRules: Array<
    (
      state: MarkdownItBlockStateLike,
      startLine: number,
      endLine: number,
      silent: boolean
    ) => boolean
  > = [];
  const inlineRules: Array<(state: MarkdownItInlineStateLike, silent: boolean) => boolean> = [];

  const makeToken = (type: string, tag: string, nesting: number): MarkdownItTokenLike => ({
    type,
    tag,
    nesting,
    content: "",
    attrs: null,
    attrSet(name: string, value: string) {
      if (!this.attrs) this.attrs = [];
      const existing = this.attrs.find(([k]) => k === name);
      if (existing) existing[1] = value;
      else this.attrs.push([name, value]);
    },
  });

  const renderInline = (src: string, env: Record<string, unknown>): string => {
    const tokens: MarkdownItTokenLike[] = [];
    const state: MarkdownItInlineStateLike = {
      src,
      pos: 0,
      posMax: src.length,
      env,
      push(type, tag, nesting) {
        const t = makeToken(type, tag, nesting);
        tokens.push(t);
        return t;
      },
    };

    while (state.pos < state.posMax) {
      let matched = false;
      for (const rule of inlineRules) {
        if (rule(state, false)) {
          matched = true;
          break;
        }
      }
      if (!matched) {
        const ch = src[state.pos++];
        const prev = tokens[tokens.length - 1];
        if (prev && prev.type === "text") {
          prev.content += ch;
        } else {
          const t = state.push("text", "", 0);
          t.content = ch;
        }
      }
    }

    return tokens
      .map((t) => {
        if (t.type === "link_open") {
          const attrs = (t.attrs || [])
            .map(([k, v]) => ` ${k}="${v}"`)
            .join("");
          return `<${t.tag}${attrs}>`;
        }
        if (t.type === "link_close") {
          return `</${t.tag}>`;
        }
        return t.content;
      })
      .join("");
  };

  const md: MarkdownItLike = {
    block: {
      ruler: {
        before(_beforeName, _ruleName, fn) {
          blockRules.unshift(fn);
        },
      },
    },
    inline: {
      ruler: {
        before(_beforeName, _ruleName, fn) {
          inlineRules.unshift(fn);
        },
        push(_ruleName, fn) {
          inlineRules.push(fn);
        },
      },
    },
    render(src: string, env: Record<string, unknown> = {}): string {
      const lines = src.split(/\r?\n/);
      const bMarks: number[] = [];
      const tShift: number[] = [];
      const eMarks: number[] = [];
      let offset = 0;
      const joined = lines.join("\n");
      for (const line of lines) {
        bMarks.push(offset);
        tShift.push(0);
        eMarks.push(offset + line.length);
        offset += line.length + 1;
      }

      const out: string[] = [];
      const blockTokens: MarkdownItTokenLike[] = [];
      const state: MarkdownItBlockStateLike = {
        src: joined,
        bMarks,
        tShift,
        eMarks,
        line: 0,
        env,
        push(type, tag, nesting) {
          const t = makeToken(type, tag, nesting);
          blockTokens.push(t);
          return t;
        },
      };

      while (state.line < lines.length) {
        const startLine = state.line;
        const beforeLen = blockTokens.length;
        let matched = false;
        for (const rule of blockRules) {
          if (rule(state, startLine, lines.length, false)) {
            matched = true;
            break;
          }
        }
        if (matched) {
          for (let i = beforeLen; i < blockTokens.length; i++) {
            out.push(blockTokens[i].content);
          }
        } else {
          const line = lines[startLine];
          if (line.trim()) {
            out.push(`<p>${renderInline(line, env)}</p>\n`);
          }
          state.line = startLine + 1;
        }
      }
      return out.join("");
    },
  };

  return md;
}

describe("VaultTree hierarchy linkage & sibling navigation", () => {
  let tmpDir: string;

  beforeEach(() => {
    tmpDir = makeTempDir("sz-tree-");
    fs.writeFileSync(
      path.join(tmpDir, "project.sailzen.md"),
      serializeNewNote({ fname: "project.sailzen", title: "SailZen Root", body: "" }),
      "utf8"
    );
    fs.writeFileSync(
      path.join(tmpDir, "project.sailzen.a.md"),
      serializeNewNote({ fname: "project.sailzen.a", title: "Part A", body: "Ref ![[project.sailzen.b]]" }),
      "utf8"
    );
    fs.writeFileSync(
      path.join(tmpDir, "project.sailzen.b.md"),
      serializeNewNote({ fname: "project.sailzen.b", title: "Part B", body: "" }),
      "utf8"
    );
    fs.writeFileSync(
      path.join(tmpDir, "journal.daily.2026.11.28.md"),
      serializeNewNote({ fname: "journal.daily.2026.11.28", title: "2026-11-28", body: "" }),
      "utf8"
    );
  });

  afterEach(() => {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  it("resolves full ancestor chain including virtual stub nodes for TreeView.reveal()", async () => {
    const idx = new VaultIndex(tmpDir);
    await idx.syncFromDisk(false);

    // Leaf note -> virtual month -> virtual year -> virtual daily -> virtual journal -> root(undefined)
    const leaf = idx.getHierarchyNode("journal.daily.2026.11.28");
    expect(leaf?.note?.fname).toBe("journal.daily.2026.11.28");

    const p1 = idx.getParentHierarchyNode("journal.daily.2026.11.28");
    expect(p1?.fname).toBe("journal.daily.2026.11");
    expect(p1?.note).toBeUndefined();
    expect(p1?.hasChildren).toBe(true);

    const p2 = idx.getParentHierarchyNode("journal.daily.2026.11");
    expect(p2?.fname).toBe("journal.daily.2026");

    const p3 = idx.getParentHierarchyNode("journal.daily.2026");
    expect(p3?.fname).toBe("journal.daily");

    const p4 = idx.getParentHierarchyNode("journal.daily");
    expect(p4?.fname).toBe("journal");

    const p5 = idx.getParentHierarchyNode("journal");
    expect(p5).toBeUndefined();

    idx.dispose();
  });

  it("respects active project namespace root filter in getParentHierarchyNode & isUnderNamespace", async () => {
    const idx = new VaultIndex(tmpDir);
    await idx.syncFromDisk(false);

    expect(idx.isUnderNamespace("project.sailzen.a", "project.sailzen")).toBe(true);
    expect(idx.isUnderNamespace("project.sailzen", "project.sailzen")).toBe(false);
    expect(idx.isUnderNamespace("journal.daily.2026.11.28", "project.sailzen")).toBe(false);

    // Direct child of rootNamespace has undefined parent in filtered tree
    expect(idx.getParentHierarchyNode("project.sailzen.a", "project.sailzen")).toBeUndefined();
    // Outside namespace returns undefined
    expect(idx.getParentHierarchyNode("journal.daily.2026.11.28", "project.sailzen")).toBeUndefined();

    idx.dispose();
  });

  it("navigates siblings and includes ![[embed]] in backlink graph", async () => {
    const idx = new VaultIndex(tmpDir);
    await idx.syncFromDisk(false);

    expect(idx.getAdjacentSiblingNote("project.sailzen.a", 1)?.fname).toBe("project.sailzen.b");
    expect(idx.getAdjacentSiblingNote("project.sailzen.b", 1)?.fname).toBe("project.sailzen.a");
    expect(idx.getAdjacentSiblingNote("project.sailzen.a", -1)?.fname).toBe("project.sailzen.b");

    // Embed ![[project.sailzen.b]] is tracked as a backlink
    const refs = idx.getReferencingNotes("project.sailzen.b");
    expect(refs.map((r) => r.fname)).toEqual(["project.sailzen.a"]);

    idx.dispose();
  });
});

describe("Heading extraction, local anchors & native Markdown Preview plugin", () => {
  it("extracts headings while skipping frontmatter and fenced code, and matches CJK slugs", () => {
    const md = `---
title: Test Note
---

# Top Title

\`\`\`markdown
# Ignored Heading Inside Fence
\`\`\`

## 第二章：架构设计

Some details here.

### 子节 A

More text.

## Next Section
`;
    const headings = extractHeadings(md);
    expect(headings.map((h) => h.text)).toEqual([
      "Top Title",
      "第二章：架构设计",
      "子节 A",
      "Next Section",
    ]);
    expect(slugifyHeading("第二章：架构设计")).toBe("第二章架构设计");
    expect(findHeadingLine(md, "第二章架构设计")).toBe(10);

    const sec = extractHeadingSection(md, "第二章：架构设计");
    expect(sec).toContain("Some details here.");
    expect(sec).toContain("### 子节 A");
    expect(sec).not.toContain("Next Section");
  });

  it("parses local #anchor wikilinks and cross-note wikilinks consistently", () => {
    const local = parseWikilinkInner("#My Heading");
    expect(local).toEqual({
      target: "",
      alias: undefined,
      anchor: "My Heading",
      targetOffsetInInner: 0,
    });

    const links = extractWikilinks("Jump to [[#Local Sec]] and ![[other.note#Part 1]].");
    expect(links).toHaveLength(2);
    expect(links[0].target).toBe("");
    expect(links[0].anchor).toBe("Local Sec");
    expect(links[1].isEmbed).toBe(true);
    expect(links[1].target).toBe("other.note");
    expect(links[1].anchor).toBe("Part 1");
  });

  it("renders wikilinks, embeds with cycle guard, and repo:// links for VS Code native Markdown Preview", () => {
    const alpha: NoteRecord = {
      fname: "project.alpha",
      fsPath: "/vault/project.alpha.md",
      id: "a1",
      title: "Alpha Architecture",
      desc: "",
      created: 0,
      updated: 0,
      tags: [],
      links: [],
      mtimeMs: 0,
      size: 0,
    };
    const bodies = new Map<string, string>([
      [
        "project.alpha",
        "## Overview\nAlpha overview body.\n\n![[project.alpha]]\n\n## Details\nDeep dive.",
      ],
    ]);

    const md = extendMarkdownItWithSailZen(createMiniMarkdownIt(), {
      resolveNote: (t) => (t.toLowerCase() === "project.alpha" ? alpha : undefined),
      readNoteBody: (n) => bodies.get(n.fname),
      resolveRepoPath: (slug) => (slug === "sailzen" ? "D:/ws/repos/SailZen" : undefined),
    });

    // Existing wikilink with relative strict-mode href
    const html1 = md.render("See [[project.alpha]] and [[Alias|project.alpha#Overview]].");
    expect(html1).toContain('href="./project.alpha.md"');
    expect(html1).toContain(">Alpha Architecture</a>");
    expect(html1).toContain('href="./project.alpha.md#overview"');
    expect(html1).toContain(">Alias</a>");

    // Missing wikilink + local heading + repo:// link
    const html2 = md.render(
      "Missing [[todo.next]], local [[#Summary]], code repo://sailzen/src/app.ts#L12"
    );
    expect(html2).toContain("sailzen-wikilink-missing");
    expect(html2).toContain('href="./todo.next.md"');
    expect(html2).toContain('href="#summary"');
    expect(html2).toContain("sailzen-repolink");
    expect(html2).toContain("sailzen/src/app.ts:L12");

    // Block transclusion embed with section filter & cycle protection (never infinite loops!)
    const embedHtml = md.render("![[project.alpha#Overview]]");
    expect(embedHtml).toContain("sailzen-embed");
    expect(embedHtml).toContain("Alpha overview body.");
    expect(embedHtml).not.toContain("Deep dive.");

    // Direct href helper check
    expect(buildWikilinkHref("project.alpha", "Overview", alpha)).toBe(
      "./project.alpha.md#overview"
    );
  });

  it("declares dual-sidebar layout and native markdown preview assets in package.json", () => {
    const pkgDir = path.resolve(__dirname, "..");
    const pkg = JSON.parse(fs.readFileSync(path.join(pkgDir, "package.json"), "utf8"));

    expect(pkg.contributes["markdown.markdownItPlugins"]).toBe(true);
    expect(pkg.contributes["markdown.previewStyles"]).toContain("./media/markdown-preview.css");

    // Left activitybar = local Vault + Calendar
    expect(pkg.contributes.viewsContainers.activitybar[0].id).toBe("sailzen-workbench");
    expect(pkg.contributes.views["sailzen-workbench"].map((v: { id: string }) => v.id)).toEqual([
      "sailzen.vaultTreeView",
      "sailzen.calendarView",
    ]);

    // Right secondarySidebar = Cloud (Rhythm, SailTick, Projects & Content)
    expect(pkg.contributes.viewsContainers.secondarySidebar[0].id).toBe("sailzen-cloud");
    expect(pkg.contributes.views["sailzen-cloud"].map((v: { id: string }) => v.id)).toEqual([
      "sailzen.rhythmView",
      "sailzen.quickChatView",
      "sailzen.projectsView",
    ]);

    // Referenced media assets exist on disk
    expect(fs.existsSync(path.join(pkgDir, "media/icons/sailzen.svg"))).toBe(true);
    expect(fs.existsSync(path.join(pkgDir, "media/icons/sailzen-cloud.svg"))).toBe(true);
    expect(fs.existsSync(path.join(pkgDir, "media/markdown-preview.css"))).toBe(true);

    // Markdown keybindings explicitly support VS Code's native custom Markdown Editor & Previewer
    const copyLinkKb = pkg.contributes.keybindings.find(
      (k: { command: string }) => k.command === "sailzen.copyNoteLink"
    );
    expect(copyLinkKb.when).toContain("activeCustomEditorId == 'vscode.markdown.editor'");
    expect(copyLinkKb.when).toContain("activeCustomEditorId == 'vscode.markdown.preview.editor'");
  });
});
