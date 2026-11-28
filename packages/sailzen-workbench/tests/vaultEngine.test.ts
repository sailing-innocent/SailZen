import * as fs from "fs";
import * as os from "os";
import * as path from "path";
import {
  extractWikilinks,
  parseNoteContent,
  serializeNewNote,
} from "../src/core/vault/noteModel";
import {
  buildDailyJournalContent,
  formatDailyJournalFname,
  getIsoDayOfWeek,
  renderTemplateBody,
} from "../src/core/vault/templateEngine";
import { VaultIndex } from "../src/core/vault/vaultIndex";

function makeTempDir(prefix: string): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

describe("noteModel & wikilink parser", () => {
  it("parses Dendron folded YAML frontmatter and extracts wikilinks while ignoring code", () => {
    const raw = `---
id: bqjz2fi325gxhdfjh4ckeqt
title: >-
  BIGS - General and Efficient
  Gaussian Splatting
desc: ''
updated: 1778841751439
created: 1740548105489
tags:
  - paper
  - 3dgs
---

See [[intro|project.bigs.intro#Method]] and [[routines.daily]].

Inline code \`[[ignored.inline]]\` must not match.

\`\`\`markdown
[[ignored.fenced]]
\`\`\`

Also [[dendron://vault/dev-note.cpp.cuda]].
`;
    const parsed = parseNoteContent("writing.paper.bigs", raw);
    expect(parsed.frontmatter.id).toBe("bqjz2fi325gxhdfjh4ckeqt");
    expect(parsed.frontmatter.title).toContain("BIGS - General and Efficient");
    expect(parsed.frontmatter.tags).toEqual(["paper", "3dgs"]);
    expect(parsed.links.map((l) => l.target)).toEqual([
      "project.bigs.intro",
      "routines.daily",
      "dev-note.cpp.cuda",
    ]);
    expect(parsed.links[0].alias).toBe("intro");
    expect(parsed.links[0].anchor).toBe("Method");
  });

  it("extracts exact target character offsets for surgical link rewriting", () => {
    const text = "Check [[My Alias|project.old.alpha#Sec1]] now.";
    const links = extractWikilinks(text, 0);
    expect(links).toHaveLength(1);
    const l = links[0];
    expect(text.slice(l.targetStart, l.targetEnd)).toBe("project.old.alpha");
  });
});

describe("templateEngine", () => {
  it("renders Dendron getDayOfWeek(fnameToDate) matching D:/vault convention", async () => {
    const friday = new Date(2026, 10, 27); // 2026-11-27 is Friday
    expect(formatDailyJournalFname(friday)).toBe("journal.daily.2026.11.27");
    expect(getIsoDayOfWeek(friday)).toBe(5);

    const rendered = renderTemplateBody(
      "- [[routines.weekday.{{ getDayOfWeek (fnameToDate) }}]]\n## Plan",
      "journal.daily.2026.11.27",
      "2026-11-27",
      friday
    );
    expect(rendered).toContain("[[routines.weekday.5]]");

    const dir = makeTempDir("sz-tpl-");
    try {
      fs.writeFileSync(
        path.join(dir, "templates.daily.md"),
        serializeNewNote({
          fname: "templates.daily",
          title: "Daily",
          body: "- [[routines.daily]]\n- [[routines.weekday.{{ getDayOfWeek (fnameToDate) }}]]\n\n## Plan\n",
        }),
        "utf8"
      );
      const built = await buildDailyJournalContent(dir, friday);
      expect(built.fname).toBe("journal.daily.2026.11.27");
      expect(built.content).toContain("[[routines.weekday.5]]");
      expect(built.content).toContain("journalNote");
    } finally {
      fs.rmSync(dir, { recursive: true, force: true });
    }
  });
});

describe("VaultIndex: indexing, cache, search, and atomic rename/refactor", () => {
  let tmpDir: string;

  beforeEach(() => {
    tmpDir = makeTempDir("sz-vault-");
    fs.writeFileSync(
      path.join(tmpDir, "project.alpha.md"),
      serializeNewNote({ fname: "project.alpha", title: "Alpha Root", body: "Child: [[project.alpha.design]]" }),
      "utf8"
    );
    fs.writeFileSync(
      path.join(tmpDir, "project.alpha.design.md"),
      serializeNewNote({ fname: "project.alpha.design", title: "Alpha Design", body: "Back to [[Root|project.alpha#Top]]" }),
      "utf8"
    );
    fs.writeFileSync(
      path.join(tmpDir, "journal.daily.2026.11.27.md"),
      serializeNewNote({
        fname: "journal.daily.2026.11.27",
        title: "2026-11-27",
        body: "Worked on [[Design Doc|project.alpha.design#Arch]] and [[project.alpha]].",
      }),
      "utf8"
    );
  });

  afterEach(() => {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  it("indexes files, builds virtual stub hierarchy, and hits cache on second sync", async () => {
    const idx = new VaultIndex(tmpDir);
    const s1 = await idx.syncFromDisk(true);
    expect(s1.totalNotes).toBe(3);
    expect(s1.parsedFiles).toBe(3);
    await idx.flushCache();

    // Virtual root domains: journal, project
    const roots = idx.getChildren("");
    expect(roots.map((r) => r.segment)).toEqual(["journal", "project"]);
    expect(roots[0].note).toBeUndefined();
    expect(roots[0].hasChildren).toBe(true);

    // Calendar lookup
    const novDays = idx.getDailyJournalDays(2026, 11);
    expect(novDays.has(27)).toBe(true);

    // Second instance should get 100% cache hits
    const idx2 = new VaultIndex(tmpDir);
    const warmCount = await idx2.loadFromCacheOnly();
    expect(warmCount).toBe(3);
    const s2 = await idx2.syncFromDisk(true);
    expect(s2.cacheHits).toBe(3);
    expect(s2.parsedFiles).toBe(0);

    idx.dispose();
    idx2.dispose();
  });

  it("atomically refactors hierarchy and rewrites all cross-vault wikilinks preserving aliases & anchors", async () => {
    const idx = new VaultIndex(tmpDir);
    await idx.syncFromDisk(false);

    const plan = await idx.planRefactorHierarchy("project.alpha", "project.archived.alpha");
    expect(plan.fileRenames).toHaveLength(2);
    expect(plan.textEdits.length).toBeGreaterThanOrEqual(3);

    await idx.applyRefactorPlanToDisk(plan);

    expect(fs.existsSync(path.join(tmpDir, "project.archived.alpha.md"))).toBe(true);
    expect(fs.existsSync(path.join(tmpDir, "project.archived.alpha.design.md"))).toBe(true);
    expect(fs.existsSync(path.join(tmpDir, "project.alpha.md"))).toBe(false);

    const journal = fs.readFileSync(
      path.join(tmpDir, "journal.daily.2026.11.27.md"),
      "utf8"
    );
    expect(journal).toContain("[[Design Doc|project.archived.alpha.design#Arch]]");
    expect(journal).toContain("[[project.archived.alpha]]");

    idx.dispose();
  });

  it("supports literal and regex batch rename with collision guard and cross-vault link rewrite", async () => {
    const idx = new VaultIndex(tmpDir);
    await idx.syncFromDisk(false);

    const plan = await idx.planBatchRename("^project\\.alpha(.*)$", "work.beta$1", {
      useRegex: true,
    });
    expect(plan.fileRenames).toHaveLength(2);
    expect(plan.textEdits.length).toBeGreaterThanOrEqual(3);

    await idx.applyRefactorPlanToDisk(plan);

    expect(fs.existsSync(path.join(tmpDir, "work.beta.md"))).toBe(true);
    expect(fs.existsSync(path.join(tmpDir, "work.beta.design.md"))).toBe(true);
    const journal = fs.readFileSync(
      path.join(tmpDir, "journal.daily.2026.11.27.md"),
      "utf8"
    );
    expect(journal).toContain("[[Design Doc|work.beta.design#Arch]]");
    expect(journal).toContain("[[work.beta]]");

    // Collision detection: mapping two files to the same name throws cleanly
    await expect(
      idx.planBatchRename("^work\\.beta.*$", "work.same", { useRegex: true })
    ).rejects.toThrow(/collision/i);

    idx.dispose();
  });
});
