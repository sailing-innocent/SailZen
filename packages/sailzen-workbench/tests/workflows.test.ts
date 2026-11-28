import * as fs from "fs";
import * as os from "os";
import * as path from "path";
import { MachineRegistry } from "../src/core/machine/machineConfig";
import { WorkbenchProjectItemDTO } from "../src/core/server/types";
import { serializeNewNote } from "../src/core/vault/noteModel";
import { VaultIndex } from "../src/core/vault/vaultIndex";
import {
  buildFallbackContextPack,
  enrichContextPackWithLocalContext,
} from "../src/features/workflows/contextPacker";
import {
  parseChapterMarkdown,
  upsertChapterSyncFrontmatter,
} from "../src/features/workflows/novelWorkflow";
import {
  appendRecordEntry,
  buildSemanticRepoLink,
} from "../src/features/workflows/projectWorkflow";

describe("Phase 3 workflows: Novel, Game/Research/Engineering, ContextPack, Pinning", () => {
  it("parses novel chapter markdown and upserts sync frontmatter cleanly without disturbing prose", () => {
    const raw = `---
id: ch001id
title: 第一章 启程
desc: ''
updated: 1795744120000
created: 1795744120000
---

星光照亮了港口，Hello World。
`;
    const parsed = parseChapterMarkdown("D:/writing/novel/ch001.md", raw);
    expect(parsed.label).toBe("第一章");
    expect(parsed.title).toBe("启程");
    expect(parsed.sourceSlug).toBe("ch001");
    expect(parsed.wordCount).toBe(9); // 7 CJK + 2 English words

    const updated = upsertChapterSyncFrontmatter(raw, {
      workId: 12,
      editionId: 34,
      nodeId: 567,
      sourceSlug: "ch001",
    });
    expect(updated).toContain("sailzen_work_id: 12");
    expect(updated).toContain("sailzen_edition_id: 34");
    expect(updated).toContain("sailzen_node_id: 567");
    expect(updated).toContain("星光照亮了港口，Hello World。");

    // Re-parse verifies round-trip IDs
    const reparsed = parseChapterMarkdown("D:/writing/novel/ch001.md", updated);
    expect(reparsed.workId).toBe(12);
    expect(reparsed.editionId).toBe(34);
    expect(reparsed.nodeId).toBe(567);
  });

  it("builds cross-machine POSIX repo:// links and rejects files outside bound repo", () => {
    const repoRoot = path.resolve(os.tmpdir(), "hat-factory");
    const targetFile = path.join(repoRoot, "src", "player", "controller.gd");

    const link = buildSemanticRepoLink({
      projectSlug: "hat-factory",
      repoRoot,
      fileFsPath: targetFile,
      line: 42,
    });
    expect(link.uri).toBe("repo://hat-factory/src/player/controller.gd#L42");
    expect(link.markdown).toBe("[controller.gd:L42](repo://hat-factory/src/player/controller.gd#L42)");

    const outsideFile = path.resolve(os.tmpdir(), "other-repo", "main.py");
    expect(() =>
      buildSemanticRepoLink({
        projectSlug: "hat-factory",
        repoRoot,
        fileFsPath: outsideFile,
      })
    ).toThrow(/outside repo root/i);
  });

  it("appends timestamped engineering/experiment logs cleanly under ## Record", () => {
    const journal = `---
title: '2026-11-28'
---

## Plan

- Finish Phase 3

## Record

- 09:00 Morning standup

## Summary

Great progress
`;
    const next = appendRecordEntry(
      journal,
      "[controller.gd:L42](repo://hat-factory/src/controller.gd#L42) — Fixed jump coyote time",
      new Date(2026, 10, 28, 10, 15)
    );
    expect(next).toContain("- 09:00 Morning standup\n- 10:15 [controller.gd:L42](repo://hat-factory/src/controller.gd#L42) — Fixed jump coyote time\n\n## Summary");
    expect(next).toContain("Great progress");
  });

  it("enriches fallback Context Pack with local Vault namespace notes and active semantic file", async () => {
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "sz-ctx-"));
    try {
      fs.writeFileSync(
        path.join(tmpDir, "project.hat-factory.gdd.md"),
        serializeNewNote({ fname: "project.hat-factory.gdd", title: "Core Loop GDD", body: "Factory mechanics" }),
        "utf8"
      );
      const idx = new VaultIndex(tmpDir);
      await idx.syncFromDisk(false);

      const proj: WorkbenchProjectItemDTO = {
        progress: {
          affair_id: 1,
          title: "Hat Factory",
          description: "Indie game prototype",
          state: "ACTIVE",
          target_date: "2026-12-31",
          days_left: 33,
          weeks_left: 4.7,
          recent_14d_hours: 12.5,
          milestones: [
            {
              id: 2,
              title: "Playable vertical slice",
              description: "",
              domain: "career",
              kind: "task_oneoff",
              state: "PLANNED",
              urgency_ddl: null,
              est_minutes: 120,
              parent_id: 1,
            },
          ],
          completion_ratio: 0,
        },
        workbench: {
          slug: "hat-factory",
          archetype: "game",
          vault_namespace: "project.hat-factory",
          repo_hints: ["hat-factory"],
          topic_id: null,
          original_work_id: null,
        },
      };

      const base = buildFallbackContextPack(proj);
      const full = enrichContextPackWithLocalContext(base, {
        machineId: "home-pc",
        activeFileSemanticLink: "[player.gd:L12](repo://hat-factory/src/player.gd#L12)",
        vaultNamespace: "project.hat-factory",
        vaultIndex: idx,
      });

      expect(full).toContain("Playable vertical slice");
      expect(full).toContain("[[Core Loop GDD|project.hat-factory.gdd]]");
      expect(full).toContain("repo://hat-factory/src/player.gd#L12");
      idx.dispose();
    } finally {
      fs.rmSync(tmpDir, { recursive: true, force: true });
    }
  });

  it("persists pinned Work IDs cleanly in ~/.sailzen/machine.json", async () => {
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "sz-pin-"));
    const cfgPath = path.join(tmpDir, "machine.json");
    try {
      const reg = new MachineRegistry(cfgPath);
      expect(reg.isWorkPinned(42)).toBe(false);
      expect(await reg.togglePinnedWork(42)).toBe(true);
      expect(reg.isWorkPinned(42)).toBe(true);

      const reg2 = new MachineRegistry(cfgPath);
      reg2.load();
      expect(reg2.isWorkPinned(42)).toBe(true);

      expect(await reg2.togglePinnedWork(42)).toBe(false);
      expect(reg2.isWorkPinned(42)).toBe(false);
    } finally {
      fs.rmSync(tmpDir, { recursive: true, force: true });
    }
  });
});
