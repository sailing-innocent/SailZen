/**
 * @file rhythmCore.test.ts
 * @brief Tests for the vscode-free sail_server Rhythm page element core.
 *
 * Covers: journal date parsing, server response normalization, the HTTP
 * client (URL composition / trailing slash / soft failure), the per-date cache
 * (isolation / TTL / error no-cache) and the providers (dashboard element with
 * explicit date, journal prefix, non-journal help, fallback).
 */
import type { PageElementRenderContext } from "@saili/unified";
import {
  buildLongTermAffairs,
  buildTodaySchedule,
  createRhythmCache,
  createRhythmCore,
  createSailServerRhythmClient,
  filterWorkCareerBlocks,
  filterWorkCareerPriorities,
  formatDateLabel,
  normalizeAffairList,
  normalizeDayDashboard,
  parseDailyJournalDate,
  renderRhythmDashboardCard,
  renderWorkFocusCard,
  todayDateStr,
} from "../rhythmCore";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const SERVER_RESPONSE = {
  date: "2026-07-18",
  day_id: 42,
  plan_version: 3,
  blocks: [
    {
      id: 1,
      affair_id: 10,
      affair_title: "深度工作",
      affair_kind: "task_oneoff",
      block_type: "focus",
      start_time: "2026-07-18T09:00:00",
      end_time: "2026-07-18T10:30:00",
      status: "PLANNED",
      energy_cost: 30,
    },
  ],
  domain_minutes: { life: 60, work: 240, career: 0 },
  energy_budget: 100,
  energy_consumed: 0,
  energy_available: 100,
  buffer_total_minutes: 60,
  buffer_free_minutes: 45,
  checkins: {
    date: "2026-07-18",
    precepts: [
      {
        affair: {
          id: 20,
          title: "23:30前入睡",
          domain: "life",
          kind: "precept",
          state: "ACTIVE",
        },
        done_today: true,
        last_result: "kept",
      },
    ],
    habits: [
      {
        affair: {
          id: 21,
          title: "阅读",
          domain: "life",
          kind: "habit",
          state: "ACTIVE",
        },
        done_today: false,
        last_result: null,
        week_done_count: 2,
        week_target: 3,
      },
    ],
  },
  priorities: [
    {
      affair: {
        id: 30,
        title: "重点项目评审",
        domain: "work",
        kind: "task_oneoff",
        state: "PLANNED",
        importance: 5,
        energy_cost: 30,
        score: 92,
      },
      reason: "今日到期 / 建议放在精力充沛时段",
      suggested_slot: "09:00-10:30",
    },
  ],
  insights: ["缓冲时间充足"],
  warnings: [],
};

function makeCtx(overrides: {
  fname: string;
  args?: any;
  raw?: string;
  fallback?: string;
  key?: string;
}): PageElementRenderContext {
  return {
    note: { id: "note-id-1", fname: overrides.fname } as any,
    key: overrides.key ?? "RHYTHM_DASHBOARD",
    args: overrides.args ?? { _: [] },
    raw: overrides.raw ?? '<sail-elem key="RHYTHM_DASHBOARD" />',
    fallback: overrides.fallback,
    fname: overrides.fname,
    vault: { fsPath: "/vault" } as any,
    vaults: [],
    config: {} as any,
  };
}

function jsonResponse(json: any, status = 200): any {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => json,
  };
}

function mockFetchRouter(opts: {
  dashboard?: any;
  affairs?: any[];
  status?: number;
}) {
  return jest.fn((url: string) => {
    if (url.includes("/affair/")) {
      return Promise.resolve(jsonResponse(opts.affairs ?? [], opts.status ?? 200));
    }
    return Promise.resolve(
      jsonResponse(opts.dashboard ?? SERVER_RESPONSE, opts.status ?? 200)
    );
  });
}

// ---------------------------------------------------------------------------
// Date helpers
// ---------------------------------------------------------------------------

describe("parseDailyJournalDate", () => {
  it("parses a daily journal fname", () => {
    expect(parseDailyJournalDate("journal.daily.2026.07.18")).toEqual({
      year: 2026,
      month: 7,
      day: 18,
    });
  });

  it("parses nested journal fnames", () => {
    expect(parseDailyJournalDate("work.journal.daily.2026.01.02")).toEqual({
      year: 2026,
      month: 1,
      day: 2,
    });
  });

  it("returns undefined for non-journal fnames", () => {
    expect(parseDailyJournalDate("journal.weekly.2026.07")).toBeUndefined();
    expect(parseDailyJournalDate("daily.2026.07.18.extra")).toBeUndefined();
    expect(parseDailyJournalDate("plain-note")).toBeUndefined();
  });
});

describe("date helpers", () => {
  it("todayDateStr formats local today", () => {
    const d = new Date(2026, 6, 18, 8, 0, 0);
    expect(todayDateStr(d)).toBe("2026-07-18");
  });

  it("formatDateLabel renders the Chinese weekday", () => {
    expect(formatDateLabel("2026-07-18")).toBe("2026-07-18 周六");
    expect(formatDateLabel("not-a-date")).toBe("not-a-date");
  });
});

// ---------------------------------------------------------------------------
// normalizeDayDashboard
// ---------------------------------------------------------------------------

describe("normalizeDayDashboard", () => {
  it("converts snake_case server payloads to camelCase", () => {
    const d = normalizeDayDashboard(SERVER_RESPONSE);
    expect(d.date).toBe("2026-07-18");
    expect(d.day_id).toBe(42);
    expect(d.plan_version).toBe(3);
    expect(d.energy_budget).toBe(100);
    expect(d.energy_available).toBe(100);
    expect(d.buffer_free_minutes).toBe(45);
    expect(d.blocks).toHaveLength(1);
    expect(d.blocks[0]).toMatchObject({
      id: 1,
      affair_title: "深度工作",
      block_type: "focus",
      status: "PLANNED",
    });
    expect(d.domain_minutes).toEqual({ life: 60, work: 240, career: 0 });
    expect(d.checkins?.precepts).toHaveLength(1);
    expect(d.checkins?.habits[0].week_done_count).toBe(2);
    expect(d.priorities).toHaveLength(1);
    expect(d.priorities[0].reason).toContain("今日到期");
    expect(d.insights).toEqual(["缓冲时间充足"]);
  });

  it("tolerates missing/extra fields", () => {
    const d = normalizeDayDashboard({
      date: "2026-07-20",
      extra_junk: 1,
    });
    expect(d.date).toBe("2026-07-20");
    expect(d.blocks).toEqual([]);
    expect(d.priorities).toEqual([]);
    expect(d.insights).toEqual([]);
    expect(d.warnings).toEqual([]);
    expect(d.checkins).toBeUndefined();
  });

  it("uses fallbackDate when date is missing", () => {
    const d = normalizeDayDashboard({}, "2026-07-20");
    expect(d.date).toBe("2026-07-20");
  });
});

// ---------------------------------------------------------------------------
// sail_server client
// ---------------------------------------------------------------------------

describe("createSailServerRhythmClient", () => {
  it("composes the URL with the date query param", async () => {
    const fetchImpl = jest
      .fn()
      .mockResolvedValue(jsonResponse(SERVER_RESPONSE));
    const client = createSailServerRhythmClient({
      resolveBaseUrl: () => "http://localhost:1974",
      fetchImpl: fetchImpl as any,
    });
    const d = await client.getDayDashboard("2026-07-18");
    expect(fetchImpl).toHaveBeenCalledTimes(1);
    const [url] = fetchImpl.mock.calls[0];
    expect(url).toBe(
      "http://localhost:1974/api/v1/rhythm/timeline/day-dashboard?date=2026-07-18"
    );
    expect(d.date).toBe("2026-07-18");
    expect(d.blocks).toHaveLength(1);
  });

  it("strips trailing slashes from the base URL", async () => {
    const fetchImpl = jest
      .fn()
      .mockResolvedValue(jsonResponse(SERVER_RESPONSE));
    const client = createSailServerRhythmClient({
      resolveBaseUrl: () => "http://192.168.1.100:1974/",
      fetchImpl: fetchImpl as any,
    });
    await client.getDayDashboard("2026-07-18");
    const [url] = fetchImpl.mock.calls[0];
    expect(url).toBe(
      "http://192.168.1.100:1974/api/v1/rhythm/timeline/day-dashboard?date=2026-07-18"
    );
  });

  it("soft-fails on non-200 responses without throwing", async () => {
    const fetchImpl = jest.fn().mockResolvedValue(jsonResponse({}, 500));
    const client = createSailServerRhythmClient({
      resolveBaseUrl: () => "http://localhost:1974",
      fetchImpl: fetchImpl as any,
    });
    const d = await client.getDayDashboard("2026-07-18");
    expect(d.error).toBe("HTTP 500");
  });

  it("soft-fails on network errors without throwing", async () => {
    const fetchImpl = jest.fn().mockRejectedValue(new Error("ECONNREFUSED"));
    const client = createSailServerRhythmClient({
      resolveBaseUrl: () => "http://localhost:1974",
      fetchImpl: fetchImpl as any,
    });
    const d = await client.getDayDashboard("2026-07-18");
    expect(d.error).toBe("ECONNREFUSED");
  });

  it("soft-fails with 请求超时 when the request aborts", async () => {
    const fetchImpl = jest.fn(
      (_url: string, init?: any) =>
        new Promise((_resolve, reject) => {
          init.signal.addEventListener("abort", () => {
            const err = new Error("aborted");
            err.name = "AbortError";
            reject(err);
          });
        })
    );
    const client = createSailServerRhythmClient({
      resolveBaseUrl: () => "http://localhost:1974",
      timeoutMs: 20,
      fetchImpl: fetchImpl as any,
    });
    const d = await client.getDayDashboard("2026-07-18");
    expect(d.error).toBe("请求超时");
  });

  it("listAffairs composes multi-value query params", async () => {
    const fetchImpl = jest.fn().mockResolvedValue(jsonResponse([]));
    const client = createSailServerRhythmClient({
      resolveBaseUrl: () => "http://localhost:1974",
      fetchImpl: fetchImpl as any,
    });
    await client.listAffairs({
      domain: ["work", "career"],
      state: ["ACTIVE", "PLANNED"],
      kind: ["venture", "async_callback"],
    });
    expect(fetchImpl).toHaveBeenCalledTimes(1);
    const [url] = fetchImpl.mock.calls[0];
    expect(url).toContain("/api/v1/rhythm/affair/");
    expect(url).toContain("domain=work");
    expect(url).toContain("domain=career");
    expect(url).toContain("state=ACTIVE");
    expect(url).toContain("state=PLANNED");
    expect(url).toContain("kind=venture");
    expect(url).toContain("kind=async_callback");
  });
});

// ---------------------------------------------------------------------------
// rhythm cache
// ---------------------------------------------------------------------------

describe("createRhythmCache", () => {
  const dashboard = normalizeDayDashboard(SERVER_RESPONSE);

  it("isolates entries per baseUrl and date", () => {
    let now = 1_000;
    const cache = createRhythmCache({
      resolveTtlMs: () => 100,
      now: () => now,
    });
    const dashboard19 = { ...dashboard, date: "2026-07-19" };
    cache.set("http://a", "2026-07-18", dashboard);
    cache.set("http://a", "2026-07-19", dashboard19);
    expect(cache.get("http://a", "2026-07-18")?.date).toBe("2026-07-18");
    expect(cache.get("http://a", "2026-07-19")?.date).toBe("2026-07-19");
    expect(cache.get("http://b", "2026-07-18")).toBeUndefined();
    expect(cache.get("http://a", "2026-07-20")).toBeUndefined();
  });

  it("expires entries after the TTL", () => {
    let now = 1_000;
    const cache = createRhythmCache({
      resolveTtlMs: () => 100,
      now: () => now,
    });
    cache.set("http://a", "2026-07-18", dashboard);
    now += 99;
    expect(cache.get("http://a", "2026-07-18")).toBe(dashboard);
    now += 2;
    expect(cache.get("http://a", "2026-07-18")).toBeUndefined();
  });

  it("never caches error entries", () => {
    const cache = createRhythmCache({ resolveTtlMs: () => 100 });
    cache.set("http://a", "2026-07-18", { ...dashboard, error: "HTTP 500" });
    expect(cache.get("http://a", "2026-07-18")).toBeUndefined();
  });

  it("clear() drops everything", () => {
    const cache = createRhythmCache({ resolveTtlMs: () => 100 });
    cache.set("http://a", "2026-07-18", dashboard);
    cache.clear();
    expect(cache.get("http://a", "2026-07-18")).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// rendering
// ---------------------------------------------------------------------------

describe("renderRhythmDashboardCard", () => {
  it("renders the date title and energy bar", () => {
    const html = renderRhythmDashboardCard(normalizeDayDashboard(SERVER_RESPONSE));
    expect(html).toContain("📅 2026-07-18 周六 · ⚡ Rhythm 日程");
    expect(html).toContain("精力预算");
    expect(html).toContain("0/100（余 100）");
  });

  it("renders timeline blocks sorted by start time", () => {
    const html = renderRhythmDashboardCard(normalizeDayDashboard(SERVER_RESPONSE));
    expect(html).toContain("09:00-10:30");
    expect(html).toContain("深度工作");
    expect(html).toContain("专注");
  });

  it("renders checkins", () => {
    const html = renderRhythmDashboardCard(normalizeDayDashboard(SERVER_RESPONSE));
    expect(html).toContain("戒律打卡");
    expect(html).toContain("23:30前入睡");
    expect(html).toContain("习惯打卡");
    expect(html).toContain("阅读");
    expect(html).toContain("2/3");
  });

  it("renders priorities with reason and suggested slot", () => {
    const html = renderRhythmDashboardCard(normalizeDayDashboard(SERVER_RESPONSE));
    expect(html).toContain("优先级事务");
    expect(html).toContain("重点项目评审");
    expect(html).toContain("今日到期");
    expect(html).toContain("09:00-10:30");
  });
});

// ---------------------------------------------------------------------------
// providers
// ---------------------------------------------------------------------------

function makeCoreWithFetch(fetchImpl: any) {
  return createRhythmCore({
    resolveBaseUrl: () => "http://localhost:1974",
    resolveCacheTtlMs: () => 60_000,
    fetchImpl,
    renderPrefixHelp: () =>
      '<div class="sail-page-element-help">RHYTHM PREFIX HELP</div>',
  });
}

describe("rhythm providers", () => {
  it("RHYTHM_DASHBOARD accepts explicit date argument", async () => {
    const fetchImpl = mockFetchRouter({});
    const core = makeCoreWithFetch(fetchImpl);
    const provider = core.createRhythmDashboardProvider();
    const html = (await provider.render(
      makeCtx({
        fname: "plain.note",
        args: { _: [], date: "2026-07-18" },
      })
    )) as string;
    const dashboardCall = fetchImpl.mock.calls.find((c) =>
      (c[0] as string).includes("/timeline/day-dashboard")
    );
    expect(dashboardCall?.[0]).toContain("date=2026-07-18");
    expect(html).toContain("📅 2026-07-18 周六 · ⚡ Rhythm 日程");
  });

  it("RHYTHM_WORK_FOCUS accepts explicit date argument and queries affairs", async () => {
    const fetchImpl = mockFetchRouter({});
    const core = makeCoreWithFetch(fetchImpl);
    const provider = core.createRhythmWorkFocusProvider();
    const html = (await provider.render(
      makeCtx({
        fname: "plain.note",
        key: "RHYTHM_WORK_FOCUS",
        args: { _: [], date: "2026-07-18" },
      })
    )) as string;
    const dashboardCall = fetchImpl.mock.calls.find((c) =>
      (c[0] as string).includes("/timeline/day-dashboard")
    );
    const affairCall = fetchImpl.mock.calls.find((c) =>
      (c[0] as string).includes("/affair/")
    );
    expect(dashboardCall?.[0]).toContain("date=2026-07-18");
    expect(affairCall?.[0]).toContain("domain=work");
    expect(affairCall?.[0]).toContain("domain=career");
    expect(html).toContain("💼 工作/事业焦点 · 2026-07-18 周六");
    expect(html).toContain("深度工作");
  });

  it("journal RHYTHM_PREFIX auto-derives date and renders compact work focus", async () => {
    const fetchImpl = mockFetchRouter({});
    const core = makeCoreWithFetch(fetchImpl);
    const provider = core.createRhythmJournalPrefixProvider();
    const html = (await provider.render(
      makeCtx({ fname: "journal.daily.2026.07.18", key: "RHYTHM_PREFIX" })
    )) as string;
    const dashboardCall = fetchImpl.mock.calls.find((c) =>
      (c[0] as string).includes("/timeline/day-dashboard")
    );
    expect(dashboardCall?.[0]).toContain("date=2026-07-18");
    expect(html).toContain("💼 工作/事业焦点 · 2026-07-18 周六");
    expect(html).toContain("今日工作/事业排程");
    expect(html).toContain("深度工作");
    expect(html).toContain("重点项目评审");
    expect(html).not.toContain("⚡ Rhythm 日程");
  });

  it("non-journal RHYTHM_PREFIX renders help", async () => {
    const fetchImpl = jest.fn();
    const core = makeCoreWithFetch(fetchImpl);
    const provider = core.createRhythmJournalPrefixProvider();
    const html = (await provider.render(
      makeCtx({ fname: "projects.todo", key: "RHYTHM_PREFIX" })
    )) as string;
    expect(fetchImpl).not.toHaveBeenCalled();
    expect(html).toContain("sail-page-element-help");
  });

  it("renders a soft notice when no work/career data is available", async () => {
    const fetchImpl = mockFetchRouter({
      dashboard: {
        date: "2026-07-18",
        day_id: 1,
        plan_version: 0,
        blocks: [],
        domain_minutes: { life: 0, work: 0, career: 0 },
        energy_budget: 100,
        energy_consumed: 0,
        energy_available: 100,
        buffer_total_minutes: 0,
        buffer_free_minutes: 0,
        priorities: [],
        insights: [],
        warnings: [],
      },
      affairs: [],
    });
    const core = makeCoreWithFetch(fetchImpl);
    const provider = core.createRhythmJournalPrefixProvider();
    const html = (await provider.render(
      makeCtx({ fname: "journal.daily.2026.07.18", key: "RHYTHM_PREFIX" })
    )) as string;
    expect(html).toContain("暂无工作/事业相关提醒");
    expect(html).not.toContain("sail-page-element-error");
  });

  it("prefers paired-marker fallback content when no work/career data", async () => {
    const fetchImpl = mockFetchRouter({
      dashboard: {
        date: "2026-07-18",
        day_id: 1,
        plan_version: 0,
        blocks: [],
        domain_minutes: { life: 0, work: 0, career: 0 },
        energy_budget: 100,
        energy_consumed: 0,
        energy_available: 100,
        buffer_total_minutes: 0,
        buffer_free_minutes: 0,
        priorities: [],
        insights: [],
        warnings: [],
      },
      affairs: [],
    });
    const core = makeCoreWithFetch(fetchImpl);
    const provider = core.createRhythmJournalPrefixProvider();
    const html = (await provider.render(
      makeCtx({
        fname: "journal.daily.2026.07.18",
        key: "RHYTHM_PREFIX",
        fallback: "自定义占位",
      })
    )) as string;
    expect(html).toContain("自定义占位");
    expect(html).not.toContain("暂无工作/事业相关提醒");
  });

  it("renders a soft fetch-failure card on network errors", async () => {
    const fetchImpl = jest.fn().mockRejectedValue(new Error("ECONNREFUSED"));
    const core = makeCoreWithFetch(fetchImpl);
    const provider = core.createRhythmJournalPrefixProvider();
    const html = (await provider.render(
      makeCtx({ fname: "journal.daily.2026.07.18", key: "RHYTHM_PREFIX" })
    )) as string;
    expect(html).toContain("获取失败：ECONNREFUSED");
    expect(html).not.toContain("sail-page-element-error");
  });

  it("caches per date so two journals never share work-focus cards", async () => {
    const byDate: Record<string, any> = {
      "2026-07-18": {
        ...SERVER_RESPONSE,
        date: "2026-07-18",
        blocks: [
          {
            ...SERVER_RESPONSE.blocks[0],
            start_time: "2026-07-18T09:00:00",
            affair_title: "18号工作",
          },
        ],
        priorities: [],
      },
      "2026-07-19": {
        ...SERVER_RESPONSE,
        date: "2026-07-19",
        blocks: [
          {
            ...SERVER_RESPONSE.blocks[0],
            start_time: "2026-07-19T09:00:00",
            affair_title: "19号工作",
          },
        ],
        priorities: [],
      },
    };
    const fetchImpl = jest.fn((url: string) => {
      if (url.includes("/affair/")) {
        return Promise.resolve(jsonResponse([]));
      }
      const date = /date=(\d{4}-\d{2}-\d{2})/.exec(url)![1];
      return Promise.resolve(jsonResponse(byDate[date]));
    });
    const core = makeCoreWithFetch(fetchImpl);
    const provider = core.createRhythmJournalPrefixProvider();

    const html18 = (await provider.render(
      makeCtx({ fname: "journal.daily.2026.07.18", key: "RHYTHM_PREFIX" })
    )) as string;
    const html19 = (await provider.render(
      makeCtx({ fname: "journal.daily.2026.07.19", key: "RHYTHM_PREFIX" })
    )) as string;
    const html18Again = (await provider.render(
      makeCtx({ fname: "journal.daily.2026.07.18", key: "RHYTHM_PREFIX" })
    )) as string;

    expect(html18).toContain("18号工作");
    expect(html19).toContain("19号工作");
    // 2 dashboards + 1 cached dashboard + 3 affair lists (uncached)
    expect(fetchImpl).toHaveBeenCalledTimes(5);
    expect(html18Again).toBe(html18);
  });

  it("RHYTHM_WORK_FOCUS renders long-term work/career affairs", async () => {
    const fetchImpl = mockFetchRouter({
      affairs: [
        {
          id: 100,
          title: "RoboCute",
          domain: "career",
          kind: "venture",
          state: "ACTIVE",
          importance: 5,
          score: 88,
          urgency_ddl: "2028-04-19T00:00:00",
        },
        {
          id: 101,
          title: "等待审阅",
          domain: "work",
          kind: "async_callback",
          state: "REVIEWING",
          importance: 4,
          score: 70,
        },
        {
          id: 102,
          title: "生活习惯",
          domain: "life",
          kind: "habit",
          state: "ACTIVE",
        },
      ],
    });
    const core = makeCoreWithFetch(fetchImpl);
    const provider = core.createRhythmWorkFocusProvider();
    const html = (await provider.render(
      makeCtx({
        fname: "journal.daily.2026.07.18",
        key: "RHYTHM_WORK_FOCUS",
      })
    )) as string;
    expect(html).toContain("长期工作/事业重点");
    expect(html).toContain("RoboCute");
    expect(html).toContain("等待审阅");
    expect(html).not.toContain("生活习惯");
  });

  it("filters life-only dashboard to work/career schedule items", () => {
    const dashboard = normalizeDayDashboard(SERVER_RESPONSE);
    const blocks = filterWorkCareerBlocks(dashboard);
    const priorities = filterWorkCareerPriorities(dashboard);
    expect(blocks).toHaveLength(1);
    expect(blocks[0].title).toBe("深度工作");
    expect(priorities).toHaveLength(1);
    expect(priorities[0].title).toBe("重点项目评审");
  });

  it("buildTodaySchedule merges blocks and priorities up to max items", () => {
    const dashboard = normalizeDayDashboard(SERVER_RESPONSE);
    const schedule = buildTodaySchedule(dashboard);
    expect(schedule).toHaveLength(2);
    expect(schedule[0].title).toBe("深度工作");
    expect(schedule[1].title).toBe("重点项目评审");
  });

  it("buildLongTermAffairs filters and sorts long-term work/career affairs", () => {
    const affairs = normalizeAffairList([
      {
        id: 1,
        title: "低优先级",
        domain: "work",
        kind: "task_maintenance",
        state: "ACTIVE",
        importance: 2,
        score: 50,
        urgency_ddl: "2028-04-19T00:00:00",
      },
      {
        id: 2,
        title: "高优先级",
        domain: "career",
        kind: "venture",
        state: "ACTIVE",
        importance: 5,
        score: 90,
        urgency_ddl: "2027-04-19T00:00:00",
      },
      {
        id: 3,
        title: "生活",
        domain: "life",
        kind: "habit",
        state: "ACTIVE",
      },
    ]);
    const items = buildLongTermAffairs(affairs);
    expect(items).toHaveLength(2);
    expect(items[0].title).toBe("高优先级");
    expect(items[1].title).toBe("低优先级");
  });

  it("renderWorkFocusCard shows empty state", () => {
    const html = renderWorkFocusCard({
      dateStr: "2026-07-18",
      todaySchedule: [],
      longTerm: [],
    });
    expect(html).toContain("💼 工作/事业焦点 · 2026-07-18 周六");
    expect(html).toContain("暂无工作/事业相关提醒");
  });
});
