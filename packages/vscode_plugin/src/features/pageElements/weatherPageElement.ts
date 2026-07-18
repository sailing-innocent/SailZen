/**
 * @file weatherPageElement.ts
 * @brief Demo page element providers: weather panel for daily journal notes.
 *
 * Registers two providers into the default page element registry:
 *
 * - `WEATHER`: renders a weather card for a hardcoded set of cities
 *   (杭州 / 上海 / 合肥), powered by the Open-Meteo API (no API key needed).
 * - `PREFIX` (override): note-aware demo — when the rendered note is a daily
 *   journal note (`journal.daily.YYYY.MM.DD`), the prefix area shows the
 *   weather card automatically; any other note keeps the built-in help.
 *
 * The provider runs inside the extension host during note rendering, so it
 * may perform async HTTP queries. Results are cached module-wide for
 * {@link WEATHER_CACHE_TTL_MS} so all daily notes share a single query.
 */
import {
  getDefaultPageElementRegistry,
  NotePageElementProvider,
  PageElementRenderContext,
  renderPageElementHelp,
  escapeHtml,
} from "@saili/unified";
import { Logger } from "../../logger";

// ---------------------------------------------------------------------------
// Configuration (hardcoded demo values)
// ---------------------------------------------------------------------------

/** Cities shown in the demo weather card. Coordinates for Open-Meteo. */
const WEATHER_CITIES: Array<{
  name: string;
  latitude: number;
  longitude: number;
}> = [
  { name: "杭州", latitude: 30.2741, longitude: 120.1551 },
  { name: "上海", latitude: 31.2304, longitude: 121.4737 },
  { name: "合肥", latitude: 31.8206, longitude: 117.2272 },
];

/** How long weather query results are reused (shared across all notes). */
const WEATHER_CACHE_TTL_MS = 30 * 60 * 1000;

/** Timeout for a single Open-Meteo request. */
const WEATHER_FETCH_TIMEOUT_MS = 10_000;

/** Daily journal fname pattern, e.g. `journal.daily.2026.07.18`. */
const DAILY_JOURNAL_FNAME_REGEX = /(^|\.)daily\.(\d{4})\.(\d{2})\.(\d{2})$/;

// ---------------------------------------------------------------------------
// Open-Meteo API client
// ---------------------------------------------------------------------------

type OpenMeteoResponse = {
  current?: {
    temperature_2m?: number;
    relative_humidity_2m?: number;
    apparent_temperature?: number;
    weather_code?: number;
    wind_speed_10m?: number;
  };
  daily?: {
    weather_code?: number[];
    temperature_2m_max?: number[];
    temperature_2m_min?: number[];
  };
};

export type CityWeather = {
  city: string;
  /** Undefined when the query for this city failed. */
  current?: {
    temperature: number;
    feelsLike?: number;
    humidity?: number;
    weatherCode: number;
    windSpeed?: number;
  };
  today?: {
    max: number;
    min: number;
    weatherCode?: number;
  };
  error?: string;
};

async function fetchCityWeather(city: {
  name: string;
  latitude: number;
  longitude: number;
}): Promise<CityWeather> {
  const params = new URLSearchParams({
    latitude: String(city.latitude),
    longitude: String(city.longitude),
    current:
      "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m",
    daily: "weather_code,temperature_2m_max,temperature_2m_min",
    timezone: "Asia/Shanghai",
    forecast_days: "1",
  });
  const url = `https://api.open-meteo.com/v1/forecast?${params.toString()}`;

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), WEATHER_FETCH_TIMEOUT_MS);
  try {
    const resp = await fetch(url, { signal: controller.signal });
    if (!resp.ok) {
      throw new Error(`HTTP ${resp.status}`);
    }
    const data = (await resp.json()) as OpenMeteoResponse;
    const cur = data.current;
    const out: CityWeather = { city: city.name };
    if (
      cur &&
      typeof cur.temperature_2m === "number" &&
      typeof cur.weather_code === "number"
    ) {
      out.current = {
        temperature: cur.temperature_2m,
        feelsLike: cur.apparent_temperature,
        humidity: cur.relative_humidity_2m,
        weatherCode: cur.weather_code,
        windSpeed: cur.wind_speed_10m,
      };
    }
    const dailyMax = data.daily?.temperature_2m_max?.[0];
    const dailyMin = data.daily?.temperature_2m_min?.[0];
    if (typeof dailyMax === "number" && typeof dailyMin === "number") {
      out.today = {
        max: dailyMax,
        min: dailyMin,
        weatherCode: data.daily?.weather_code?.[0],
      };
    }
    if (!out.current && !out.today) {
      out.error = "API 返回数据不完整";
    }
    return out;
  } catch (err: any) {
    return {
      city: city.name,
      error: err?.name === "AbortError" ? "请求超时" : err?.message ?? String(err),
    };
  } finally {
    clearTimeout(timer);
  }
}

// ---------------------------------------------------------------------------
// Shared weather cache (one query serves all notes within the TTL)
// ---------------------------------------------------------------------------

let weatherCache: { data: CityWeather[]; expiresAt: number } | undefined;

async function getWeatherForAllCities(): Promise<CityWeather[]> {
  if (weatherCache && weatherCache.expiresAt > Date.now()) {
    return weatherCache.data;
  }
  const data = await Promise.all(WEATHER_CITIES.map(fetchCityWeather));
  weatherCache = { data, expiresAt: Date.now() + WEATHER_CACHE_TTL_MS };
  return data;
}

/** Test/dev hook: drop the shared weather cache. */
export function clearWeatherCache(): void {
  weatherCache = undefined;
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

function describeWeatherCode(code?: number): [string, string] {
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

function renderWeatherCard(opts: {
  title: string;
  cities: CityWeather[];
  footer?: string;
}): string {
  const rows = opts.cities
    .map((cw) => {
      if (cw.error || !cw.current) {
        return [
          `<div style="${CITY_ROW_STYLE}">`,
          `<span><strong>${escapeHtml(cw.city)}</strong></span>`,
          `<span style="${MUTED_STYLE}">获取失败${cw.error ? `：${escapeHtml(cw.error)}` : ""}</span>`,
          `</div>`,
        ].join("");
      }
      const [emoji, label] = describeWeatherCode(cw.current.weatherCode);
      const range = cw.today
        ? ` <span style="${MUTED_STYLE}">${Math.round(cw.today.min)}° ~ ${Math.round(cw.today.max)}°</span>`
        : "";
      return [
        `<div style="${CITY_ROW_STYLE}">`,
        `<span><strong>${escapeHtml(cw.city)}</strong>&nbsp;${emoji} ${escapeHtml(label)}</span>`,
        `<span><strong>${Math.round(cw.current.temperature)}°C</strong>${range}</span>`,
        `</div>`,
      ].join("");
    })
    .join("");

  const footer = opts.footer
    ? `<div style="${MUTED_STYLE}; font-size: 0.8em; margin-top: 6px;">${opts.footer}</div>`
    : "";

  return [
    `<div class="sail-weather-card" style="${CARD_STYLE}">`,
    `<div style="${CARD_TITLE_STYLE}">${opts.title}</div>`,
    rows,
    footer,
    `</div>`,
  ].join("");
}

// ---------------------------------------------------------------------------
// Daily journal detection
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

const WEEKDAYS_CN = ["日", "一", "二", "三", "四", "五", "六"];

function formatJournalDate(d: { year: number; month: number; day: number }) {
  const date = new Date(d.year, d.month - 1, d.day);
  const weekday = WEEKDAYS_CN[date.getDay()];
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.year}-${pad(d.month)}-${pad(d.day)} 周${weekday}`;
}

// ---------------------------------------------------------------------------
// Providers
// ---------------------------------------------------------------------------

async function renderWeatherForCities(ctx: PageElementRenderContext) {
  const cities = await getWeatherForAllCities();
  const allFailed = cities.every((c) => c.error);
  if (allFailed) {
    // Soft failure for the journal top area: prefer the paired-marker
    // fallback content if the user provided one.
    if (ctx.fallback) {
      return `<div style="${MUTED_STYLE}">${escapeHtml(ctx.fallback)}</div>`;
    }
  }
  return renderWeatherCard({
    title: "🌤 当前天气",
    cities,
    footer: `数据来自 Open-Meteo · 更新于 ${new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })}`,
  });
}

/** Explicit `<sail-elem key="WEATHER" />` element. */
export function createWeatherProvider(): NotePageElementProvider {
  return {
    key: "WEATHER",
    title: "Weather",
    description: `显示 ${WEATHER_CITIES.map((c) => c.name).join(" / ")} 的当前天气（Open-Meteo，demo 硬编码城市）`,
    usage: '<sail-elem key="WEATHER" />',
    render: renderWeatherForCities,
  };
}

/**
 * Note-aware `PREFIX` override: daily journal notes get the weather card in
 * their top area automatically; other notes keep the built-in help.
 */
export function createJournalPrefixProvider(): NotePageElementProvider {
  return {
    key: "PREFIX",
    title: "Note Prefix",
    description:
      "顶部区域。Daily Journal 笔记（journal.daily.*）自动显示天气卡片，其他笔记显示帮助",
    usage: '<sail-elem key="PREFIX" />',
    render: async (ctx) => {
      const journalDate = parseDailyJournalDate(ctx.fname);
      if (journalDate) {
        const cities = await getWeatherForAllCities();
        return renderWeatherCard({
          title: `📅 ${formatJournalDate(journalDate)} · 🌤 当前天气`,
          cities,
          footer: `数据来自 Open-Meteo · 更新于 ${new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })}`,
        });
      }
      // Not a daily journal: keep the default help content.
      return renderPageElementHelp({
        key: "PREFIX",
        raw: ctx.raw,
        providers: getDefaultPageElementRegistry().list(),
      });
    },
  };
}

// ---------------------------------------------------------------------------
// Registration
// ---------------------------------------------------------------------------

/**
 * Register the demo page element providers. Idempotent: safe to call on
 * every activation (override replaces any previous registration).
 */
export function registerWeatherPageElementProviders(): void {
  const registry = getDefaultPageElementRegistry();
  registry.register(createWeatherProvider(), { override: true });
  registry.register(createJournalPrefixProvider(), { override: true });
  Logger.info({
    ctx: "registerWeatherPageElementProviders",
    msg: "weather page element providers registered",
  });
}
