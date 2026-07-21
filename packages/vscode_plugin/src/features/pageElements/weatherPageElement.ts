/**
 * @file weatherPageElement.ts
 * @brief VSCode glue layer for the sail_server-backed weather page elements.
 *
 * All actual logic (sail_server client, per-date cache, provider factories,
 * card rendering) lives in the vscode-free {@link weatherCore} module so it
 * can also run inside the standalone engine child process (prod mode) and in
 * jest tests. This file only wires VSCode-specific concerns:
 *
 * - reads `sailzen.sailServer.baseUrl` / `sailzen.sailServer.weatherCacheTtlMinutes`
 *   from the workspace configuration;
 * - forwards core log lines to the extension {@link Logger};
 * - registers the providers into the default page element registry on
 *   activation (dev-mode engine renders inside the extension host).
 *
 * The public API of this module is unchanged from the original Open-Meteo
 * demo so `features/pageElements/index.ts` and `_extension.ts` need no edits.
 */
import * as vscode from "vscode";
import {
  getDefaultPageElementRegistry,
  NotePageElementProvider,
  renderPageElementHelp,
} from "@saili/unified";
import { Logger } from "../../logger";
import {
  CityWeatherPayload,
  createWeatherCore,
  DEFAULT_WEATHER_CACHE_TTL_MS,
  WeatherCore,
} from "./weatherCore";

// ---------------------------------------------------------------------------
// Re-exports (stable public API)
// ---------------------------------------------------------------------------

export { parseDailyJournalDate } from "./weatherCore";

/** Backwards-compatible alias of the core payload type. */
export type CityWeather = CityWeatherPayload;

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

const DEFAULT_SAIL_SERVER_BASE_URL = "http://localhost:1974";

function resolveBaseUrl(): string {
  return (
    vscode.workspace
      .getConfiguration("sailzen.sailServer")
      .get<string>("baseUrl") ?? DEFAULT_SAIL_SERVER_BASE_URL
  );
}

function resolveCacheTtlMs(): number {
  const minutes = vscode.workspace
    .getConfiguration("sailzen.sailServer")
    .get<number>("weatherCacheTtlMinutes");
  if (typeof minutes === "number" && Number.isFinite(minutes) && minutes > 0) {
    return minutes * 60 * 1000;
  }
  return DEFAULT_WEATHER_CACHE_TTL_MS;
}

// ---------------------------------------------------------------------------
// Core singleton (config is re-read on every query / registration)
// ---------------------------------------------------------------------------

let core: WeatherCore | undefined;

function getCore(): WeatherCore {
  if (!core) {
    core = createWeatherCore({
      resolveBaseUrl,
      resolveCacheTtlMs,
      renderPrefixHelp: (ctx) =>
        renderPageElementHelp({
          key: "PREFIX",
          raw: ctx.raw,
          providers: getDefaultPageElementRegistry().list(),
        }),
      log: (level, msg) => {
        const payload = { ctx: "weatherPageElement", msg };
        if (level === "error") {
          Logger.error(payload);
        } else if (level === "warn") {
          Logger.warn(payload);
        } else if (level === "debug") {
          Logger.debug(payload);
        } else {
          Logger.info(payload);
        }
      },
    });
  }
  return core;
}

// ---------------------------------------------------------------------------
// Providers (delegating to the core)
// ---------------------------------------------------------------------------

/** Explicit `<sail-elem key="WEATHER" />` element. */
export function createWeatherProvider(): NotePageElementProvider {
  return getCore().createWeatherProvider();
}

/**
 * Note-aware `PREFIX` override: daily journal notes get the weather card of
 * their date in the top area; other notes keep the built-in help.
 */
export function createJournalPrefixProvider(): NotePageElementProvider {
  return getCore().createJournalPrefixProvider();
}

/** Test/dev hook: drop the per-date weather cache. */
export function clearWeatherCache(): void {
  core?.clearCache();
}

// ---------------------------------------------------------------------------
// Registration
// ---------------------------------------------------------------------------

/**
 * Register the weather page element providers. Idempotent: safe to call on
 * every activation (override replaces any previous registration).
 */
export function registerWeatherPageElementProviders(): void {
  getCore().register(getDefaultPageElementRegistry());
  Logger.info({
    ctx: "registerWeatherPageElementProviders",
    msg: "weather page element providers registered (sail_server backend)",
  });
}
