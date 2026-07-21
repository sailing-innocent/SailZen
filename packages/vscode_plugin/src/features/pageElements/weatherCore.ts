/**
 * @file weatherCore.ts
 * @brief sail_server-backed weather page element core (vscode-free).
 *
 * This module is deliberately free of any `vscode` / `Logger` imports so it
 * can run in every process that performs note rendering:
 *
 * - the VSCode extension host (dev mode engine, via `weatherPageElement.ts`);
 * - the standalone engine child process (prod mode, via `server.ts`);
 * - plain jest unit tests.
 *
 * Weather data comes from the remote sail_server
 * (`GET /api/v1/life/weather?date=YYYY-MM-DD`), which periodically pulls
 * Open-Meteo forecast/archive data into `days.ref["weather"]`:
 *
 * - future / today dates hold `kind="forecast"` data, overwritten on every
 *   server-side update round ("逐步更新");
 * - past dates hold immutable `kind="record"` data consolidated from the
 *   Open-Meteo archive ("天气记录").
 *
 * The providers are date-aware: for a daily journal note
 * (`journal.daily.YYYY.MM.DD`) they render the weather of *that* date, so
 * switching the focused editor between journals of different dates switches
 * the previewed weather accordingly. The registry-level cache key already
 * contains `note.id`, and the module-level cache here is keyed by
 * `${baseUrl}|${date}`, so different dates never pollute each other.
 *
 * Known caching behavior: while a note stays open and unchanged, the
 * webview/engine render caches may keep showing previously rendered HTML;
 * server-side weather updates surface after the provider `cacheTtlMs`
 * (default 30min) or when the preview is reopened. This is pre-existing
 * render-cache semantics, not something this module changes.
 *
 * NOTE: this module has **zero runtime imports** — `@saili/unified` is only
 * imported for types (erased at compile time). The unified-based help
 * renderer is injected via {@link WeatherCoreDeps.renderPrefixHelp} by the
 * VSCode glue layer / engine entry so the module stays loadable in jest
 * without transforming unified's compiled ESM output.
 */
import type {
  NotePageElementProvider,
  PageElementRegistry,
  PageElementRenderContext,
} from "@saili/unified";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** forecast: 逐步更新的预报；record: 当天过去后固化的天气实录（不可变）。 */
export type WeatherKind = "forecast" | "record";

/** camelCase 的单城市天气（由服务器 snake_case 响应归一化而来）。 */
export type CityWeatherPayload = {
  city: string;
  kind: WeatherKind;
  weatherCode?: number;
  tempMax?: number;
  tempMin?: number;
  tempCurrent?: number;
  humidity?: number;
  windSpeed?: number;
  source?: string;
  fetchedAt?: string;
};

/** 某一天的天气查询结果（client 永不抛错，失败走 error 软失败）。 */
export type DayWeather = {
  /** YYYY-MM-DD */
  date: string;
  available: boolean;
  kind: WeatherKind;
  cities: CityWeatherPayload[];
  updatedAt?: string;
  /** 网络/HTTP 失败原因；设置时 available=false。 */
  error?: string;
};

export type WeatherLogFn = (
  level: "debug" | "info" | "warn" | "error",
  msg: string
) => void;

export type WeatherCoreDeps = {
  /** 解析 sail_server 地址，例如 http://localhost:1974（每次查询时调用）。 */
  resolveBaseUrl: () => string;
  /** provider/registry 缓存 TTL（毫秒），默认 30min。创建 provider 时读取。 */
  resolveCacheTtlMs?: () => number;
  /** 测试注入的 fetch 实现；默认全局 fetch。 */
  fetchImpl?: typeof fetch;
  /** 可选日志回调，由 vscode 胶水层注入 Logger。 */
  log?: WeatherLogFn;
  /**
   * 非 journal 笔记的 PREFIX 帮助内容渲染器。由胶水层注入
   * （基于 unified 的 renderPageElementHelp）；缺省时使用内置简版帮助。
   */
  renderPrefixHelp?: (ctx: PageElementRenderContext) => string;
};

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Default client-side cache TTL for weather queries (30 minutes). */
export const DEFAULT_WEATHER_CACHE_TTL_MS = 30 * 60 * 1000;

/** Default timeout for a single sail_server weather request. */
export const DEFAULT_WEATHER_FETCH_TIMEOUT_MS = 8_000;

/** Daily journal fname pattern, e.g. `journal.daily.2026.07.18`. */
const DAILY_JOURNAL_FNAME_REGEX = /(^|\.)daily\.(\d{4})\.(\d{2})\.(\d{2})$/;

const DATE_ARG_REGEX = /^\d{4}-\d{2}-\d{2}$/;

const WEEKDAYS_CN = ["日", "一", "二", "三", "四", "五", "六"];

/** Escape a string for safe inclusion in HTML text/attribute content. */
function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

// ---------------------------------------------------------------------------
// Date helpers
// ---------------------------------------------------------------------------

/** Extract the journal date from a daily journal fname, if it is one. */
export function parseDailyJournalDate(
  fname: string
): { year: number; month: number; day: number } | undefined {
  const m = DAILY_JOURNAL_FNAME_REGEX.exec(fname);
  if (!m) return undefined;
  return {
    year: Number(m[2]),
    month: Number(m[3]),
    day: Number(m[4]),
  };
}

const pad2 = (n: number) => String(n).padStart(2, "0");

/** `YYYY-MM-DD` for the local current day. */
export function todayDateStr(now: Date = new Date()): string {
  return `${now.getFullYear()}-${pad2(now.getMonth() + 1)}-${pad2(now.getDate())}`;
}

/** Aggregate kind for a date, mirroring the server: past -> record. */
export function kindForDate(dateStr: string, todayStr: string = todayDateStr()): WeatherKind {
  return dateStr < todayStr ? "record" : "forecast";
}

/** `2026-07-18 周六` style label for a `YYYY-MM-DD` string. */
export function formatDateLabel(dateStr: string): string {
  const m = DATE_ARG_REGEX.exec(dateStr);
  if (!m) return dateStr;
  const [y, mo, d] = dateStr.split("-").map((s) => Number(s));
  const weekday = WEEKDAYS_CN[new Date(y, mo - 1, d).getDay()];
  return `${dateStr} 周${weekday}`;
}

function journalDateStr(fname: string): string | undefined {
  const d = parseDailyJournalDate(fname);
  if (!d) return undefined;
  return `${d.year}-${pad2(d.month)}-${pad2(d.day)}`;
}

// ---------------------------------------------------------------------------
// sail_server weather client
// ---------------------------------------------------------------------------

export type SailServerWeatherClient = {
  getDayWeather(dateStr: string): Promise<DayWeather>;
};

function unavailableDay(dateStr: string, error?: string): DayWeather {
  return {
    date: dateStr,
    available: false,
    kind: kindForDate(dateStr),
    cities: [],
    error,
  };
}

function numOrUndef(v: unknown): number | undefined {
  return typeof v === "number" && Number.isFinite(v) ? v : undefined;
}

/**
 * Normalize the server response (snake_case) into {@link DayWeather}
 * (camelCase). Pure function, tolerant to missing/extra fields.
 */
export function normalizeDayWeather(json: any, fallbackDate?: string): DayWeather {
  const date =
    typeof json?.date === "string" && json.date ? json.date : fallbackDate ?? "";
  const kind: WeatherKind = json?.kind === "record" ? "record" : "forecast";
  const citiesRaw: any[] = Array.isArray(json?.cities) ? json.cities : [];
  const cities: CityWeatherPayload[] = citiesRaw
    .filter((c) => c && typeof c === "object")
    .map((c) => ({
      city: String(c.city ?? ""),
      kind: c.kind === "record" ? ("record" as const) : ("forecast" as const),
      weatherCode: numOrUndef(c.weather_code),
      tempMax: numOrUndef(c.temp_max),
      tempMin: numOrUndef(c.temp_min),
      tempCurrent: numOrUndef(c.temp_current),
      humidity: numOrUndef(c.humidity),
      windSpeed: numOrUndef(c.wind_speed),
      source: typeof c.source === "string" ? c.source : undefined,
      fetchedAt: typeof c.fetched_at === "string" ? c.fetched_at : undefined,
    }));
  return {
    date,
    available: Boolean(json?.available) && cities.length > 0,
    kind,
    cities,
    updatedAt: typeof json?.updated_at === "string" ? json.updated_at : undefined,
  };
}

/**
 * HTTP client for the sail_server weather API. Never throws: network and
 * HTTP failures are returned as `{ available: false, error }` so the weather
 * card fails soft instead of triggering the registry error box.
 */
export function createSailServerWeatherClient(deps: {
  resolveBaseUrl: () => string;
  timeoutMs?: number;
  fetchImpl?: typeof fetch;
}): SailServerWeatherClient {
  const fetchImpl = deps.fetchImpl ?? fetch;
  const timeoutMs = deps.timeoutMs ?? DEFAULT_WEATHER_FETCH_TIMEOUT_MS;
  return {
    async getDayWeather(dateStr: string): Promise<DayWeather> {
      const baseUrl = deps.resolveBaseUrl().replace(/\/+$/, "");
      const url = `${baseUrl}/api/v1/life/weather?date=${encodeURIComponent(dateStr)}`;
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), timeoutMs);
      try {
        const resp = await fetchImpl(url, { signal: controller.signal });
        if (!resp.ok) {
          return unavailableDay(dateStr, `HTTP ${resp.status}`);
        }
        const json = await resp.json();
        return normalizeDayWeather(json, dateStr);
      } catch (err: any) {
        const msg =
          err?.name === "AbortError" ? "请求超时" : err?.message ?? String(err);
        return unavailableDay(dateStr, msg);
      } finally {
        clearTimeout(timer);
      }
    },
  };
}

// ---------------------------------------------------------------------------
// Per-date weather cache
// ---------------------------------------------------------------------------

export type WeatherCache = {
  get(baseUrl: string, dateStr: string): DayWeather | undefined;
  set(baseUrl: string, dateStr: string, data: DayWeather): void;
  clear(): void;
};

/**
 * Module-scope cache keyed by `${baseUrl}|${date}`. Entries for consolidated
 * records (`kind === "record"`, immutable by definition) live 8x longer than
 * the configured TTL; entries carrying an `error` are never cached so the
 * next render retries.
 */
export function createWeatherCache(opts: {
  resolveTtlMs: () => number;
  now?: () => number;
}): WeatherCache {
  const map = new Map<string, { data: DayWeather; expiresAt: number }>();
  const now = opts.now ?? Date.now;
  const keyOf = (baseUrl: string, dateStr: string) => `${baseUrl}|${dateStr}`;
  return {
    get(baseUrl, dateStr) {
      const key = keyOf(baseUrl, dateStr);
      const entry = map.get(key);
      if (!entry) return undefined;
      if (entry.expiresAt <= now()) {
        map.delete(key);
        return undefined;
      }
      return entry.data;
    },
    set(baseUrl, dateStr, data) {
      if (data.error) return; // 失败不缓存，下次渲染重试
      const ttlMs = opts.resolveTtlMs();
      const ttl = data.kind === "record" && data.available ? ttlMs * 8 : ttlMs;
      map.set(keyOf(baseUrl, dateStr), { data, expiresAt: now() + ttl });
    },
    clear() {
      map.clear();
    },
  };
}

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------

/** WMO weather code -> [emoji, 中文描述] */
const WMO_MAP: Record<number, [string, string]> = {
  0: ["☀️", "晴"],
  1: ["🌤", "大部晴朗"],
  2: ["⛅", "局部多云"],
  3: ["☁️", "阴"],
  45: ["🌫", "雾"],
  48: ["🌫", "冻雾"],
  51: ["🌦", "小毛毛雨"],
  53: ["🌦", "毛毛雨"],
  55: ["🌧", "浓毛毛雨"],
  56: ["🌧", "冻毛毛雨"],
  57: ["🌧", "强冻毛毛雨"],
  61: ["🌧", "小雨"],
  63: ["🌧", "中雨"],
  65: ["🌧", "大雨"],
  66: ["🌧", "冻雨"],
  67: ["🌧", "强冻雨"],
  71: ["🌨", "小雪"],
  73: ["🌨", "中雪"],
  75: ["❄️", "大雪"],
  77: ["❄️", "雪粒"],
  80: ["🌦", "小阵雨"],
  81: ["🌧", "阵雨"],
  82: ["🌧", "强阵雨"],
  85: ["🌨", "小阵雪"],
  86: ["🌨", "大阵雪"],
  95: ["⛈", "雷暴"],
  96: ["⛈", "雷暴伴冰雹"],
  99: ["⛈", "强雷暴伴冰雹"],
};

export function describeWeatherCode(code?: number): [string, string] {
  if (code === undefined) return ["❓", "未知"];
  return WMO_MAP[code] ?? ["❓", `未知(${code})`];
}

const CARD_STYLE = [
  "border: 1px solid var(--vscode-panel-border, #d0d7de)",
  "border-radius: 8px",
  "padding: 10px 14px",
  "margin: 8px 0",
  "background: var(--vscode-textBlockQuote-background, rgba(127,127,127,0.06))",
].join("; ");

const CARD_TITLE_STYLE = [
  "font-weight: 600",
  "margin-bottom: 6px",
  "color: var(--vscode-foreground, #24292f)",
].join("; ");

const CITY_ROW_STYLE = [
  "display: flex",
  "justify-content: space-between",
  "align-items: baseline",
  "padding: 2px 0",
].join("; ");

const MUTED_STYLE = "color: var(--vscode-descriptionForeground, #6a737d)";

const KIND_BADGE_STYLE = [
  "font-size: 0.75em",
  "border: 1px solid var(--vscode-panel-border, #d0d7de)",
  "border-radius: 4px",
  "padding: 0 4px",
  "margin-left: 6px",
  MUTED_STYLE,
].join("; ");

const KIND_LABEL: Record<WeatherKind, string> = {
  forecast: "预报",
  record: "实录",
};

/** `HH:mm` extracted from an ISO timestamp; undefined when unparseable. */
function timeLabel(iso?: string): string | undefined {
  if (!iso) return undefined;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return undefined;
  return `${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
}

/**
 * Render the weather card for one day. Title includes the date label and the
 * forecast/record badge: `📅 2026-07-18 周六 · 🌤 天气实录`.
 */
export function renderDayWeatherCard(opts: {
  dayWeather: DayWeather;
  /** e.g. `2026-07-18 周六`; defaults to the raw date. */
  dateLabel?: string;
}): string {
  const { dayWeather } = opts;
  const kindLabel = KIND_LABEL[dayWeather.kind];
  const dateLabel = opts.dateLabel ?? formatDateLabel(dayWeather.date);
  const title = `📅 ${escapeHtml(dateLabel)} · 🌤 天气${kindLabel}`;

  const rows = dayWeather.cities
    .map((cw) => {
      const [emoji, label] = describeWeatherCode(cw.weatherCode);
      const current =
        typeof cw.tempCurrent === "number"
          ? `<strong>${Math.round(cw.tempCurrent)}°C</strong> `
          : "";
      const range =
        typeof cw.tempMin === "number" && typeof cw.tempMax === "number"
          ? `<span style="${MUTED_STYLE}">${Math.round(cw.tempMin)}° ~ ${Math.round(cw.tempMax)}°</span>`
          : "";
      const badge = `<span style="${KIND_BADGE_STYLE}">${KIND_LABEL[cw.kind]}</span>`;
      return [
        `<div style="${CITY_ROW_STYLE}">`,
        `<span><strong>${escapeHtml(cw.city)}</strong>&nbsp;${emoji} ${escapeHtml(label)}</span>`,
        `<span>${current}${range}${badge}</span>`,
        `</div>`,
      ].join("");
    })
    .join("");

  const updated = timeLabel(dayWeather.updatedAt);
  const footer = `<div style="${MUTED_STYLE}; font-size: 0.8em; margin-top: 6px;">数据来自 sail_server${updated ? ` · 更新于 ${updated}` : ""}</div>`;

  return [
    `<div class="sail-weather-card" style="${CARD_STYLE}">`,
    `<div style="${CARD_TITLE_STYLE}">${title}</div>`,
    rows,
    footer,
    `</div>`,
  ].join("");
}

/** Soft "no data" notice; prefers paired-marker fallback content. */
function renderUnavailable(dateStr: string, fallback?: string): string {
  if (fallback) {
    return `<div style="${MUTED_STYLE}">${escapeHtml(fallback)}</div>`;
  }
  return `<div style="${MUTED_STYLE}">📅 ${escapeHtml(formatDateLabel(dateStr))} · 该日期暂无天气数据</div>`;
}

/** Soft fetch-failure card (never throws, never triggers registry error box). */
function renderFetchError(dateStr: string, error: string): string {
  return [
    `<div class="sail-weather-card" style="${CARD_STYLE}">`,
    `<div style="${CARD_TITLE_STYLE}">📅 ${escapeHtml(formatDateLabel(dateStr))} · 🌤 天气</div>`,
    `<div style="${MUTED_STYLE}">获取失败：${escapeHtml(error)}</div>`,
    `</div>`,
  ].join("");
}

// ---------------------------------------------------------------------------
// Providers
// ---------------------------------------------------------------------------

type WeatherProviderDeps = WeatherCoreDeps & {
  client: SailServerWeatherClient;
  cache: WeatherCache;
};

/** Query (with cache) the weather of one date. */
async function queryDayWeather(
  deps: WeatherProviderDeps,
  dateStr: string
): Promise<DayWeather> {
  const baseUrl = deps.resolveBaseUrl().replace(/\/+$/, "");
  const cached = deps.cache.get(baseUrl, dateStr);
  if (cached) return cached;
  const data = await deps.client.getDayWeather(dateStr);
  if (data.error) {
    deps.log?.("warn", `[weather] query ${dateStr} failed: ${data.error}`);
  } else {
    deps.cache.set(baseUrl, dateStr, data);
  }
  return data;
}

/** Render the weather card (or soft failure) for `dateStr`. */
async function renderWeatherForDate(
  deps: WeatherProviderDeps,
  dateStr: string,
  fallback?: string
): Promise<string> {
  const day = await queryDayWeather(deps, dateStr);
  if (day.error) return renderFetchError(dateStr, day.error);
  if (!day.available) return renderUnavailable(dateStr, fallback);
  return renderDayWeatherCard({ dayWeather: day });
}

function resolveCacheTtlMs(deps: WeatherCoreDeps): number {
  return deps.resolveCacheTtlMs?.() ?? DEFAULT_WEATHER_CACHE_TTL_MS;
}

/**
 * Explicit `<sail-elem key="WEATHER" />` element. Optional `date="YYYY-MM-DD"`
 * argument overrides the date; without it the date is derived from the note's
 * journal fname, falling back to today.
 */
export function createWeatherProvider(
  deps: WeatherProviderDeps
): NotePageElementProvider {
  return {
    key: "WEATHER",
    title: "Weather",
    description:
      "显示指定日期（date 参数 / 笔记日期 / 今天）的天气，数据来自 sail_server",
    usage: '<sail-elem key="WEATHER" date="2026-07-18" />',
    cacheTtlMs: resolveCacheTtlMs(deps),
    render: async (ctx: PageElementRenderContext) => {
      const dateArg = ctx.args?.date;
      const dateStr =
        typeof dateArg === "string" && DATE_ARG_REGEX.test(dateArg)
          ? dateArg
          : journalDateStr(ctx.fname) ?? todayDateStr();
      return renderWeatherForDate(deps, dateStr, ctx.fallback);
    },
  };
}

/**
 * Note-aware `PREFIX` override: daily journal notes get the weather card of
 * *their* date in the top area; other notes keep the built-in help.
 */
export function createJournalPrefixProvider(
  deps: WeatherProviderDeps
): NotePageElementProvider {
  return {
    key: "PREFIX",
    title: "Note Prefix",
    description:
      "顶部区域。Daily Journal 笔记（journal.daily.*）自动显示该日天气卡片，其他笔记显示帮助",
    usage: '<sail-elem key="PREFIX" />',
    cacheTtlMs: resolveCacheTtlMs(deps),
    render: async (ctx: PageElementRenderContext) => {
      const dateStr = journalDateStr(ctx.fname);
      if (dateStr) {
        return renderWeatherForDate(deps, dateStr, ctx.fallback);
      }
      // Not a daily journal: keep the default help content.
      if (deps.renderPrefixHelp) {
        return deps.renderPrefixHelp(ctx);
      }
      return [
        `<div class="sail-page-element-help" style="${MUTED_STYLE}">`,
        `Sail Page Element: <code>${escapeHtml(ctx.raw)}</code> renders dynamic content for the top area of the note.`,
        `</div>`,
      ].join("");
    },
  };
}

// ---------------------------------------------------------------------------
// Core factory
// ---------------------------------------------------------------------------

export type WeatherCore = {
  client: SailServerWeatherClient;
  cache: WeatherCache;
  createWeatherProvider: () => NotePageElementProvider;
  createJournalPrefixProvider: () => NotePageElementProvider;
  /** Drop the module-level per-date weather cache (test/dev hook). */
  clearCache: () => void;
  /** Register both providers (idempotent, override semantics). */
  register: (registry: PageElementRegistry) => void;
};

export function createWeatherCore(deps: WeatherCoreDeps): WeatherCore {
  const cache = createWeatherCache({
    resolveTtlMs: () => resolveCacheTtlMs(deps),
  });
  const client = createSailServerWeatherClient({
    resolveBaseUrl: deps.resolveBaseUrl,
    fetchImpl: deps.fetchImpl,
  });
  const providerDeps: WeatherProviderDeps = { ...deps, client, cache };
  return {
    client,
    cache,
    createWeatherProvider: () => createWeatherProvider(providerDeps),
    createJournalPrefixProvider: () => createJournalPrefixProvider(providerDeps),
    clearCache: () => cache.clear(),
    register: (registry: PageElementRegistry) => {
      registry.register(createWeatherProvider(providerDeps), { override: true });
      registry.register(createJournalPrefixProvider(providerDeps), {
        override: true,
      });
      deps.log?.("info", "[weather] page element providers registered");
    },
  };
}
