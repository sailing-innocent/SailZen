import { getDurationMilliseconds } from "@saili/common-server";
import fs from "fs-extra";
import path from "path";

/**
 * Segments of the startup pipeline. All segments are optional so partial
 * failures or skipped stages never block the record from being written.
 *
 * - `spawnServer`: time to spawn the engine server subprocess
 * - `wsInit`: {@link WorkspaceActivator.init} (workspace setup + migrations + clone)
 * - `minimalInit`: engine minimal init (schema + priority notes + stubs)
 * - `fullInit`: engine full index (all notes parsed, backlinks + fuse built)
 * - `treeViewInit`: tree view registration
 * - `deferredWork`: non-critical work deferred to idle time
 */
export type StartupDurationSegments = {
  spawnServer?: number;
  wsInit?: number;
  minimalInit?: number;
  fullInit?: number;
  treeViewInit?: number;
  deferredWork?: number;
};

export type StartupPerfRecord = {
  timestamp: string;
  version: string;
  activationSucceeded: boolean;
  noteCount: number;
  vaultCount: number;
  cacheMisses?: number;
  /**
   * Which startup mode was used. `"fast"` is the fast-first three stage
   * startup, `"full"` is the legacy blocking startup.
   */
  mode?: "fast" | "full";
  durationMs: StartupDurationSegments & {
    reloadWorkspace: number;
  };
};

const MAX_RECORDS = 50;

/**
 * Records startup performance segments to `<wsRoot>/logs/startup-perf.jsonl`.
 *
 * Segments are recorded in-memory via {@link StartupProfiler.recordSegment}
 * from anywhere in the activation pipeline and are merged into the record the
 * next time {@link StartupProfiler.write} is called. Recording is
 * best-effort and never throws.
 */
export class StartupProfiler {
  private static _segments: Map<string, number> = new Map();

  /**
   * Record a segment duration in milliseconds under `name`. If a segment with
   * the same name was already recorded, it is overwritten.
   */
  static recordSegment(name: string, durationMs: number): void {
    try {
      if (!Number.isFinite(durationMs) || durationMs < 0) {
        return;
      }
      StartupProfiler._segments.set(name, durationMs);
    } catch (_err) {
      // non-critical, never throw
    }
  }

  /**
   * Convenience wrapper around `process.hrtime()`: stop the timer started at
   * `start` and record it under `name`.
   */
  static recordSegmentSince(name: string, start: [number, number]): void {
    try {
      StartupProfiler.recordSegment(name, getDurationMilliseconds(start));
    } catch (_err) {
      // non-critical, never throw
    }
  }

  /** Read a previously recorded segment (ms), if any. */
  static getSegment(name: string): number | undefined {
    return StartupProfiler._segments.get(name);
  }

  /**
   * Drain all recorded segments. Used by {@link StartupProfiler.write} so
   * that a written record contains each segment exactly once.
   */
  static consumeSegments(): Record<string, number> {
    const out: Record<string, number> = {};
    try {
      StartupProfiler._segments.forEach((value, key) => {
        out[key] = value;
      });
      StartupProfiler._segments.clear();
    } catch (_err) {
      // non-critical, never throw
    }
    return out;
  }

  /** Reset all recorded segments. Mostly useful for tests. */
  static reset(): void {
    StartupProfiler._segments.clear();
  }

  static write(wsRoot: string, record: StartupPerfRecord): void {
    try {
      const logDir = path.join(wsRoot, "logs");
      fs.ensureDirSync(logDir);
      const logFile = path.join(logDir, "startup-perf.jsonl");
      // Merge any segments that were recorded since the last write. Explicit
      // fields on `record.durationMs` win over recorded segments.
      const segments = StartupProfiler.consumeSegments();
      const line =
        JSON.stringify({
          ...record,
          durationMs: { ...segments, ...record.durationMs },
        }) + "\n";
      fs.appendFileSync(logFile, line, { encoding: "utf8" });
      StartupProfiler._trim(logFile);
    } catch (_err) {
      // non-critical, never throw
    }
  }

  private static _trim(filePath: string): void {
    try {
      const content = fs.readFileSync(filePath, "utf8");
      const lines = content.split("\n").filter((l) => l.trim().length > 0);
      if (lines.length > MAX_RECORDS) {
        const trimmed = lines.slice(lines.length - MAX_RECORDS).join("\n") + "\n";
        fs.writeFileSync(filePath, trimmed, "utf8");
      }
    } catch (_err) {
      // non-critical
    }
  }
}
