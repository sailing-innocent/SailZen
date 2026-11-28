/**
 * @file rhythmPageElement.ts
 * @brief VSCode glue layer for the sail_server-backed Rhythm page elements.
 *
 * All actual logic (sail_server client, per-date cache, provider factories,
 * card rendering) lives in the vscode-free {@link rhythmCore} module so it
 * can also run inside the standalone engine child process (prod mode) and in
 * jest tests. This file only wires VSCode-specific concerns:
 *
 * - reads `sailzen.sailServer.baseUrl` / `sailzen.sailServer.rhythmCacheTtlMinutes`
 *   from the workspace configuration;
 * - forwards core log lines to the extension {@link Logger};
 * - registers the providers into the default page element registry on
 *   activation (dev-mode engine renders inside the extension host).
 */
import * as vscode from "vscode";
import {
  getDefaultPageElementRegistry,
  NotePageElementProvider,
  renderPageElementHelp,
} from "@saili/unified";
import { Logger } from "../../logger";
import {
  createRhythmCore,
  DEFAULT_RHYTHM_CACHE_TTL_MS,
  PriorityAffair,
  RhythmBlock,
  RhythmDashboard,
  RhythmCore,
} from "./rhythmCore";

// ---------------------------------------------------------------------------
// Re-exports (stable public API)
// ---------------------------------------------------------------------------

export { parseDailyJournalDate } from "./rhythmCore";
export type { PriorityAffair, RhythmDashboard, RhythmBlock };

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
    .get<number>("rhythmCacheTtlMinutes");
  if (typeof minutes === "number" && Number.isFinite(minutes) && minutes > 0) {
    return minutes * 60 * 1000;
  }
  return DEFAULT_RHYTHM_CACHE_TTL_MS;
}

// ---------------------------------------------------------------------------
// Core singleton (config is re-read on every query / registration)
// ---------------------------------------------------------------------------

let core: RhythmCore | undefined;

function getCore(): RhythmCore {
  if (!core) {
    core = createRhythmCore({
      resolveBaseUrl,
      resolveCacheTtlMs,
      renderPrefixHelp: (ctx) =>
        renderPageElementHelp({
          key: "RHYTHM_PREFIX",
          raw: ctx.raw,
          providers: getDefaultPageElementRegistry().list(),
        }),
      log: (level, msg) => {
        const payload = { ctx: "rhythmPageElement", msg };
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

/** Explicit `<sail-elem key="RHYTHM_DASHBOARD" />` element. */
export function createRhythmDashboardProvider(): NotePageElementProvider {
  return getCore().createRhythmDashboardProvider();
}

/**
 * Explicit `<sail-elem key="RHYTHM_WORK_FOCUS" />` element: compact work/career
 * reminder card for a given date.
 */
export function createRhythmWorkFocusProvider(): NotePageElementProvider {
  return getCore().createRhythmWorkFocusProvider();
}

/**
 * Note-aware `RHYTHM_PREFIX`: daily journal notes get the work/career focus card
 * of their date in the top area; other notes keep the built-in help.
 */
export function createRhythmJournalPrefixProvider(): NotePageElementProvider {
  return getCore().createRhythmJournalPrefixProvider();
}

/** Test/dev hook: drop the per-date rhythm cache. */
export function clearRhythmCache(): void {
  core?.clearCache();
}

// ---------------------------------------------------------------------------
// Registration
// ---------------------------------------------------------------------------

/**
 * Register the rhythm page element providers. Idempotent: safe to call on
 * every activation (override replaces any previous registration).
 */
export function registerRhythmPageElementProviders(): void {
  getCore().register(getDefaultPageElementRegistry());
  Logger.info({
    ctx: "registerRhythmPageElementProviders",
    msg: "rhythm page element providers registered (sail_server backend)",
  });
}
