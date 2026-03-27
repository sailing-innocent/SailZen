import fs from "fs-extra";
import path from "path";

export type StartupPerfRecord = {
  timestamp: string;
  version: string;
  activationSucceeded: boolean;
  noteCount: number;
  vaultCount: number;
  cacheMisses?: number;
  durationMs: {
    reloadWorkspace: number;
  };
};

const MAX_RECORDS = 50;

export class StartupProfiler {
  static write(wsRoot: string, record: StartupPerfRecord): void {
    try {
      const logDir = path.join(wsRoot, "logs");
      fs.ensureDirSync(logDir);
      const logFile = path.join(logDir, "startup-perf.jsonl");
      const line = JSON.stringify(record) + "\n";
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
