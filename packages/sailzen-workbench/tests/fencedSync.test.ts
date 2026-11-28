import * as fs from "fs";
import * as os from "os";
import * as path from "path";
import {
  collectVaultContentNotes,
  MANAGED_META_END,
  MANAGED_META_START,
  mergeManagedMetaFence,
  writeWorkClipsToVault,
} from "../src/core/server/fencedSync";
import { serializeNewNote } from "../src/core/vault/noteModel";
import { VaultIndex } from "../src/core/vault/vaultIndex";

describe("Content 2.0 fenced bidirectional sync", () => {
  let tmpDir: string;

  beforeEach(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "sz-fenced-"));
  });

  afterEach(() => {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  it("merges managed metadata fence without touching handwritten notes", () => {
    const existing = `---
id: abc123
title: Designing Data-Intensive Applications
---

${MANAGED_META_START}
- Progress: 20%
${MANAGED_META_END}

## 我的手写读书心得

这一章讲复制与共识非常透彻。
`;
    const incoming = `---
title: DDIA
---

${MANAGED_META_START}
- Progress: 65%
- Clips: [[read.ddia.clips]]
${MANAGED_META_END}

## Default template section
`;

    const merged = mergeManagedMetaFence(existing, incoming);
    expect(merged).toContain("- Progress: 65%");
    expect(merged).not.toContain("- Progress: 20%");
    expect(merged).toContain("## 我的手写读书心得");
    expect(merged).toContain("这一章讲复制与共识非常透彻。");
    expect(merged).not.toContain("Default template section");
  });

  it("collects only read.*/topic.*/study.* notes for upstream index sync", async () => {
    fs.writeFileSync(
      path.join(tmpDir, "read.ddia.md"),
      serializeNewNote({ fname: "read.ddia", title: "DDIA", body: "分布式系统经典著作。" }),
      "utf8"
    );
    fs.writeFileSync(
      path.join(tmpDir, "study.tech.graphics.md"),
      serializeNewNote({ fname: "study.tech.graphics", title: "Graphics", body: "实时渲染笔记。" }),
      "utf8"
    );
    fs.writeFileSync(
      path.join(tmpDir, "journal.daily.2026.11.27.md"),
      serializeNewNote({ fname: "journal.daily.2026.11.27", title: "2026-11-27", body: "私密日记不上传" }),
      "utf8"
    );

    const idx = new VaultIndex(tmpDir);
    await idx.syncFromDisk(false);

    const items = await collectVaultContentNotes(idx, "home-pc");
    expect(items.map((i) => i.fname).sort()).toEqual(["read.ddia", "study.tech.graphics"]);
    const studyItem = items.find((i) => i.fname === "study.tech.graphics")!;
    expect(studyItem.pillar).toBe("tech");
    expect(studyItem.content_hash).toHaveLength(64);

    idx.dispose();
  });

  it("writes clips and merges reading card safely via writeWorkClipsToVault", async () => {
    const cardFile = path.join(tmpDir, "read.ddia.md");
    fs.writeFileSync(
      cardFile,
      `---
id: keepme
title: DDIA
---

我的原始笔记必须完整保留！
`,
      "utf8"
    );

    const res = await writeWorkClipsToVault(tmpDir, {
      work_id: 7,
      work_title: "DDIA",
      vault_slug: "ddia",
      clips_filename: "read.ddia.clips.md",
      card_filename: "read.ddia.md",
      annotation_count: 2,
      clips_markdown: "# Clips\n- quote 1\n",
      card_markdown: `${MANAGED_META_START}\n- Progress: 80%\n${MANAGED_META_END}\n`,
    });

    expect(res.cardAction).toBe("updated");
    const updatedCard = fs.readFileSync(cardFile, "utf8");
    expect(updatedCard).toContain("id: keepme");
    expect(updatedCard).toContain("- Progress: 80%");
    expect(updatedCard).toContain("我的原始笔记必须完整保留！");
    expect(fs.readFileSync(path.join(tmpDir, "read.ddia.clips.md"), "utf8")).toContain("quote 1");
  });
});
