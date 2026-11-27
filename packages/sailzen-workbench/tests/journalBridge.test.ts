import { WorkbenchBootstrapDTO } from "../src/core/server/types";
import {
  formatRhythmSnapshotMarkdown,
  injectRhythmFencedSection,
  RHYTHM_FENCE_END,
  RHYTHM_FENCE_START,
} from "../src/features/editor/journalBridge";

const SAMPLE_BOOT: WorkbenchBootstrapDTO = {
  date: "2026-11-27",
  timeline: {
    date: "2026-11-27",
    day_id: 1,
    plan_version: 2,
    ai_rationale: "上午专注架构重构，下午留白复盘。",
    blocks: [
      {
        id: 10,
        day_id: 1,
        affair_id: 100,
        affair_title: "SailZen Workbench MVP",
        affair_kind: "venture",
        affair_domain: "career",
        block_type: "focus",
        start_time: "2026-11-27T09:30:00",
        end_time: "2026-11-27T11:30:00",
        status: "DONE",
        pinned: false,
        plan_version: 2,
        ref: {},
      },
      {
        id: 11,
        day_id: 1,
        affair_id: null,
        affair_title: null,
        affair_kind: null,
        affair_domain: null,
        block_type: "focus",
        start_time: "2026-11-27T14:00:00",
        end_time: "2026-11-27T16:00:00",
        status: "PLANNED",
        pinned: false,
        plan_version: 2,
        ref: { label: "小说大纲推进" },
      },
    ],
    completed_minutes: 120,
    planned_minutes: 240,
  },
  projects: [],
  focus_affairs: [],
  overdue_affairs: [],
  topics: [],
  pending_tickets: [],
  degraded: [],
};

describe("journalBridge", () => {
  it("injects Rhythm fence under ## Plan without disturbing handwritten notes and updates idempotently", () => {
    const initial = `---
id: abc
title: '2026-11-27'
---

## Plan

手写的今日想法

## Record

完成了第一版
`;
    const block1 = formatRhythmSnapshotMarkdown(SAMPLE_BOOT);
    const once = injectRhythmFencedSection(initial, block1);

    expect(once).toContain(RHYTHM_FENCE_START);
    expect(once).toContain(RHYTHM_FENCE_END);
    expect(once).toContain("- [x] 09:30-11:30 SailZen Workbench MVP");
    expect(once).toContain("- [ ] 14:00-16:00 小说大纲推进");
    expect(once).toContain("手写的今日想法");
    expect(once).toContain("完成了第一版");

    // Second injection replaces ONLY inside the fence
    const block2 = `${RHYTHM_FENCE_START}\nUPDATED\n${RHYTHM_FENCE_END}`;
    const twice = injectRhythmFencedSection(once, block2);
    expect(twice.match(new RegExp(RHYTHM_FENCE_START, "g"))).toHaveLength(1);
    expect(twice).toContain("UPDATED");
    expect(twice).toContain("手写的今日想法");
    expect(twice).toContain("完成了第一版");
  });
});
