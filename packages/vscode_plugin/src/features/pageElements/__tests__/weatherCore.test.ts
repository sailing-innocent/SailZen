/**
 * @file weatherCore.test.ts
 * @brief Tests for the vscode-free sail_server weather page element core.
 *
 * Covers: journal date parsing, server response normalization, the HTTP
 * client (URL composition / trailing slash / soft failure), the per-date
 * cache (isolation / TTL / record long TTL) and the providers (journal card
 * rendering with forecast/record badges, non-journal help, soft failures).
 */
import {
  createSailServerWeatherClient,
  createWeatherCache,
  createWeatherCore,
  DayWeather,
  describeWeatherCode,
  formatDateLabel,
  kindForDate,
  normalizeDayWeather,
  parseDailyJournalDate,
  renderDayWeatherCard,
} from "../weatherCore";
import type { PageElementRenderContext } from "@saili/unified";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const SERVER_RESPONSE = {
  date: "2026-07-18",
  available: true,
  kind: "record",
  cities: [
    {
      city: "杭州",
      kind: "record",
      weather_code: 61,
      temp_max: 33.5,
      temp_min: 26.1,
      temp_current: null,
      humidity: null,
      wind_speed: null,
      source: "open-meteo-archive",
      fetched_at: "2026-07-19T00:10:00+08:00",
    },
  ],
  updated_at: "2026-07-18T08:30:00+08:00",
};

function makeCtx(overrides: {
  fname: string;
  args?: any;
  raw?: string;
  fallback?: string;
}): PageElementRenderContext {
  return {
    note: { id: "note-id-1", fname: overrides.fname } as any,
    key: "PREFIX",
    args: overrides.args ?? { _: [] },
    raw: overrides.raw ?? '<sail-elem key="PREFIX" />',
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

// ---------------------------------------------------------------------------
// parseDailyJournalDate / date helpers
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
  it("kindForDate aggregates past dates as record", () => {
    expect(kindForDate("2026-07-18", "2026-07-20")).toBe("record");
    expect(kindForDate("2026-07-20", "2026-07-20")).toBe("forecast");
    expect(kindForDate("2026-07-21", "2026-07-20")).toBe("forecast");
  });

  it("formatDateLabel renders the Chinese weekday", () => {
    // 2026-07-18 is a Saturday
    expect(formatDateLabel("2026-07-18")).toBe("2026-07-18 周六");
    expect(formatDateLabel("not-a-date")).toBe("not-a-date");
  });

  it("describeWeatherCode maps WMO codes", () => {
    expect(describeWeatherCode(0)).toEqual(["☀️", "晴"]);
    expect(describeWeatherCode(999)).toEqual(["❓", "未知(999)"]);
    expect(describeWeatherCode(undefined)).toEqual(["❓", "未知"]);
  });
});

// ---------------------------------------------------------------------------
// normalizeDayWeather
// ---------------------------------------------------------------------------

describe("normalizeDayWeather", () => {
  it("converts snake_case server payloads to camelCase", () => {
    const day = normalizeDayWeather(SERVER_RESPONSE);
    expect(day.date).toBe("2026-07-18");
    expect(day.available).toBe(true);
    expect(day.kind).toBe("record");
    expect(day.updatedAt).toBe("2026-07-18T08:30:00+08:00");
    expect(day.cities).toHaveLength(1);
    const c = day.cities[0];
    expect(c.city).toBe("杭州");
    expect(c.kind).toBe("record");
    expect(c.weatherCode).toBe(61);
    expect(c.tempMax).toBe(33.5);
    expect(c.tempMin).toBe(26.1);
    expect(c.tempCurrent).toBeUndefined();
    expect(c.source).toBe("open-meteo-archive");
    expect(c.fetchedAt).toBe("2026-07-19T00:10:00+08:00");
  });

  it("tolerates missing/extra fields", () => {
    const day = normalizeDayWeather({
      date: "2026-07-20",
      available: true,
      kind: "forecast",
      cities: [{ city: "上海", kind: "forecast", extra_junk: 1 }, null, 42],
      updated_at: null,
      something_else: "ignored",
    });
    expect(day.cities).toHaveLength(1);
    expect(day.cities[0]).toMatchObject({ city: "上海", kind: "forecast" });
    expect(day.cities[0].tempMax).toBeUndefined();
    expect(day.updatedAt).toBeUndefined();
  });

  it("forces available=false when cities is empty", () => {
    const day = normalizeDayWeather({
      date: "2026-07-20",
      available: true,
      kind: "forecast",
      cities: [],
    });
    expect(day.available).toBe(false);
  });

  it("uses fallbackDate when date is missing", () => {
    const day = normalizeDayWeather({ kind: "forecast" }, "2026-07-20");
    expect(day.date).toBe("2026-07-20");
  });
});

// ---------------------------------------------------------------------------
// sail_server client
// ---------------------------------------------------------------------------

describe("createSailServerWeatherClient", () => {
  it("composes the URL with the date query param", async () => {
    const fetchImpl = jest
      .fn()
      .mockResolvedValue(jsonResponse(SERVER_RESPONSE));
    const client = createSailServerWeatherClient({
      resolveBaseUrl: () => "http://localhost:1974",
      fetchImpl: fetchImpl as any,
    });
    const day = await client.getDayWeather("2026-07-18");
    expect(fetchImpl).toHaveBeenCalledTimes(1);
    const [url] = fetchImpl.mock.calls[0];
    expect(url).toBe("http://localhost:1974/api/v1/life/weather?date=2026-07-18");
    expect(day.available).toBe(true);
    expect(day.kind).toBe("record");
  });

  it("strips trailing slashes from the base URL", async () => {
    const fetchImpl = jest
      .fn()
      .mockResolvedValue(jsonResponse(SERVER_RESPONSE));
    const client = createSailServerWeatherClient({
      resolveBaseUrl: () => "http://192.168.1.100:1974/",
      fetchImpl: fetchImpl as any,
    });
    await client.getDayWeather("2026-07-18");
    const [url] = fetchImpl.mock.calls[0];
    expect(url).toBe(
      "http://192.168.1.100:1974/api/v1/life/weather?date=2026-07-18"
    );
  });

  it("soft-fails on non-200 responses without throwing", async () => {
    const fetchImpl = jest.fn().mockResolvedValue(jsonResponse({}, 500));
    const client = createSailServerWeatherClient({
      resolveBaseUrl: () => "http://localhost:1974",
      fetchImpl: fetchImpl as any,
    });
    const day = await client.getDayWeather("2026-07-18");
    expect(day.available).toBe(false);
    expect(day.error).toBe("HTTP 500");
  });

  it("soft-fails on network errors without throwing", async () => {
    const fetchImpl = jest.fn().mockRejectedValue(new Error("ECONNREFUSED"));
    const client = createSailServerWeatherClient({
      resolveBaseUrl: () => "http://localhost:1974",
      fetchImpl: fetchImpl as any,
    });
    const day = await client.getDayWeather("2026-07-18");
    expect(day.available).toBe(false);
    expect(day.error).toBe("ECONNREFUSED");
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
    const client = createSailServerWeatherClient({
      resolveBaseUrl: () => "http://localhost:1974",
      timeoutMs: 20,
      fetchImpl: fetchImpl as any,
    });
    const day = await client.getDayWeather("2026-07-18");
    expect(day.available).toBe(false);
    expect(day.error).toBe("请求超时");
  });
});

// ---------------------------------------------------------------------------
// weather cache
// ---------------------------------------------------------------------------

describe("createWeatherCache", () => {
  const forecastDay: DayWeather = {
    date: "2026-07-20",
    available: true,
    kind: "forecast",
    cities: [],
  };
  const recordDay: DayWeather = {
    date: "2026-07-18",
    available: true,
    kind: "record",
    cities: [],
  };

  it("isolates entries per baseUrl and date", () => {
    let now = 1_000;
    const cache = createWeatherCache({
      resolveTtlMs: () => 100,
      now: () => now,
    });
    cache.set("http://a", "2026-07-18", recordDay);
    cache.set("http://a", "2026-07-19", forecastDay);
    expect(cache.get("http://a", "2026-07-18")).toBe(recordDay);
    expect(cache.get("http://a", "2026-07-19")).toBe(forecastDay);
    expect(cache.get("http://b", "2026-07-18")).toBeUndefined();
    expect(cache.get("http://a", "2026-07-20")).toBeUndefined();
  });

  it("expires entries after the TTL", () => {
    let now = 1_000;
    const cache = createWeatherCache({
      resolveTtlMs: () => 100,
      now: () => now,
    });
    cache.set("http://a", "2026-07-20", forecastDay);
    now += 99;
    expect(cache.get("http://a", "2026-07-20")).toBe(forecastDay);
    now += 2; // 101 > 100
    expect(cache.get("http://a", "2026-07-20")).toBeUndefined();
  });

  it("keeps record entries 8x longer", () => {
    let now = 1_000;
    const cache = createWeatherCache({
      resolveTtlMs: () => 100,
      now: () => now,
    });
    cache.set("http://a", "2026-07-18", recordDay);
    now += 500; // forecast 早已过期
    expect(cache.get("http://a", "2026-07-18")).toBe(recordDay);
    now += 301; // 801 > 800
    expect(cache.get("http://a", "2026-07-18")).toBeUndefined();
  });

  it("never caches error entries", () => {
    const cache = createWeatherCache({ resolveTtlMs: () => 100 });
    cache.set("http://a", "2026-07-20", {
      ...forecastDay,
      available: false,
      error: "HTTP 500",
    });
    expect(cache.get("http://a", "2026-07-20")).toBeUndefined();
  });

  it("clear() drops everything", () => {
    const cache = createWeatherCache({ resolveTtlMs: () => 100 });
    cache.set("http://a", "2026-07-18", recordDay);
    cache.clear();
    expect(cache.get("http://a", "2026-07-18")).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// rendering
// ---------------------------------------------------------------------------

describe("renderDayWeatherCard", () => {
  it("renders the date title with the record badge", () => {
    const html = renderDayWeatherCard({
      dayWeather: normalizeDayWeather(SERVER_RESPONSE),
    });
    expect(html).toContain("📅 2026-07-18 周六 · 🌤 天气实录");
    expect(html).toContain("杭州");
    expect(html).toContain("🌧 小雨");
    expect(html).toContain("26° ~ 34°");
    expect(html).toContain(">实录</span>");
    expect(html).toContain("数据来自 sail_server · 更新于 08:30");
  });

  it("renders forecast cards with current temperature", () => {
    const html = renderDayWeatherCard({
      dayWeather: {
        date: "2026-07-20",
        available: true,
        kind: "forecast",
        cities: [
          { city: "上海", kind: "forecast", weatherCode: 0, tempMax: 35, tempMin: 27, tempCurrent: 31 },
        ],
        updatedAt: "2026-07-20T09:05:00+08:00",
      },
    });
    expect(html).toContain("🌤 天气预报");
    expect(html).toContain("31°C");
    expect(html).toContain("27° ~ 35°");
    expect(html).toContain(">预报</span>");
  });
});

// ---------------------------------------------------------------------------
// providers
// ---------------------------------------------------------------------------

function makeCoreWithFetch(fetchImpl: any) {
  return createWeatherCore({
    resolveBaseUrl: () => "http://localhost:1974",
    resolveCacheTtlMs: () => 60_000,
    fetchImpl,
    renderPrefixHelp: () =>
      '<div class="sail-page-element-help">PREFIX HELP</div>',
  });
}

describe("weather providers", () => {
  it("journal PREFIX renders the weather card of the journal date", async () => {
    const fetchImpl = jest
      .fn()
      .mockResolvedValue(jsonResponse(SERVER_RESPONSE));
    const core = makeCoreWithFetch(fetchImpl);
    const provider = core.createJournalPrefixProvider();
    const html = (await provider.render(
      makeCtx({ fname: "journal.daily.2026.07.18" })
    )) as string;
    const [url] = fetchImpl.mock.calls[0];
    expect(url).toContain("date=2026-07-18");
    expect(html).toContain("📅 2026-07-18 周六 · 🌤 天气实录");
    expect(html).toContain("杭州");
  });

  it("non-journal PREFIX renders the built-in help", async () => {
    const fetchImpl = jest.fn();
    const core = makeCoreWithFetch(fetchImpl);
    const provider = core.createJournalPrefixProvider();
    const html = (await provider.render(
      makeCtx({ fname: "projects.todo" })
    )) as string;
    expect(fetchImpl).not.toHaveBeenCalled();
    expect(html).toContain("sail-page-element-help");
  });

  it("renders a soft notice when no data is available (no throw)", async () => {
    const fetchImpl = jest.fn().mockResolvedValue(
      jsonResponse({
        date: "2026-07-18",
        available: false,
        kind: "record",
        cities: [],
        updated_at: null,
      })
    );
    const core = makeCoreWithFetch(fetchImpl);
    const provider = core.createJournalPrefixProvider();
    const html = (await provider.render(
      makeCtx({ fname: "journal.daily.2026.07.18" })
    )) as string;
    expect(html).toContain("该日期暂无天气数据");
    expect(html).not.toContain("sail-page-element-error");
  });

  it("prefers paired-marker fallback content when no data", async () => {
    const fetchImpl = jest.fn().mockResolvedValue(
      jsonResponse({
        date: "2026-07-18",
        available: false,
        kind: "record",
        cities: [],
        updated_at: null,
      })
    );
    const core = makeCoreWithFetch(fetchImpl);
    const provider = core.createJournalPrefixProvider();
    const html = (await provider.render(
      makeCtx({ fname: "journal.daily.2026.07.18", fallback: "自定义占位" })
    )) as string;
    expect(html).toContain("自定义占位");
    expect(html).not.toContain("该日期暂无天气数据");
  });

  it("renders a soft fetch-failure card on network errors (no throw)", async () => {
    const fetchImpl = jest.fn().mockRejectedValue(new Error("ECONNREFUSED"));
    const core = makeCoreWithFetch(fetchImpl);
    const provider = core.createJournalPrefixProvider();
    const html = (await provider.render(
      makeCtx({ fname: "journal.daily.2026.07.18" })
    )) as string;
    expect(html).toContain("获取失败：ECONNREFUSED");
    expect(html).not.toContain("sail-page-element-error");
  });

  it("WEATHER provider honors the explicit date argument", async () => {
    const fetchImpl = jest
      .fn()
      .mockResolvedValue(jsonResponse(SERVER_RESPONSE));
    const core = makeCoreWithFetch(fetchImpl);
    const provider = core.createWeatherProvider();
    const html = (await provider.render(
      makeCtx({
        fname: "plain.note",
        args: { _: [], date: "2026-07-18" },
      })
    )) as string;
    const [url] = fetchImpl.mock.calls[0];
    expect(url).toContain("date=2026-07-18");
    expect(html).toContain("📅 2026-07-18 周六");
  });

  it("caches per date so two journals never share weather", async () => {
    const byDate: Record<string, any> = {
      "2026-07-18": {
        date: "2026-07-18",
        available: true,
        kind: "record",
        cities: [
          { city: "杭州", kind: "record", weather_code: 61, temp_max: 33, temp_min: 26 },
        ],
        updated_at: "2026-07-19T00:10:00+08:00",
      },
      "2026-07-19": {
        date: "2026-07-19",
        available: true,
        kind: "record",
        cities: [
          { city: "杭州", kind: "record", weather_code: 0, temp_max: 36, temp_min: 27 },
        ],
        updated_at: "2026-07-20T00:10:00+08:00",
      },
    };
    const fetchImpl = jest.fn((url: string) => {
      const date = /date=(\d{4}-\d{2}-\d{2})/.exec(url)![1];
      return Promise.resolve(jsonResponse(byDate[date]));
    });
    const core = makeCoreWithFetch(fetchImpl);
    const provider = core.createJournalPrefixProvider();

    const html18 = (await provider.render(
      makeCtx({ fname: "journal.daily.2026.07.18" })
    )) as string;
    const html19 = (await provider.render(
      makeCtx({ fname: "journal.daily.2026.07.19" })
    )) as string;
    const html18Again = (await provider.render(
      makeCtx({ fname: "journal.daily.2026.07.18" })
    )) as string;

    expect(html18).toContain("2026-07-18 周六");
    expect(html18).toContain("26° ~ 33°");
    expect(html19).toContain("2026-07-19 周日");
    expect(html19).toContain("27° ~ 36°");
    // 第二次渲染命中缓存，不再请求
    expect(fetchImpl).toHaveBeenCalledTimes(2);
    expect(html18Again).toBe(html18);
  });
});
