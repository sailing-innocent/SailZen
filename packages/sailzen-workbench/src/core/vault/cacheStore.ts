import * as fs from "fs";
import * as path from "path";
import { NoteRecord } from "./noteModel";

const CACHE_VERSION = 1;
const CACHE_FILENAME = ".sailzen-index.json";

export interface VaultIndexCachePayload {
  version: number;
  generatedAt: number;
  entries: Record<string, NoteRecord>;
}

export class VaultCacheStore {
  private readonly cachePath: string;
  private saveTimer: NodeJS.Timeout | null = null;

  constructor(notesDir: string) {
    this.cachePath = path.join(notesDir, CACHE_FILENAME);
  }

  get filePath(): string {
    return this.cachePath;
  }

  async load(): Promise<Map<string, NoteRecord>> {
    const map = new Map<string, NoteRecord>();
    try {
      const raw = await fs.promises.readFile(this.cachePath, "utf8");
      const parsed = JSON.parse(raw) as Partial<VaultIndexCachePayload>;
      if (parsed.version !== CACHE_VERSION || !parsed.entries) {
        return map;
      }
      for (const [key, entry] of Object.entries(parsed.entries)) {
        if (entry && typeof entry.fname === "string" && typeof entry.mtimeMs === "number") {
          map.set(key.toLowerCase(), entry);
        }
      }
    } catch {
      // Missing or corrupted cache: start clean without failing
    }
    return map;
  }

  async saveNow(notes: Map<string, NoteRecord>): Promise<void> {
    if (this.saveTimer) {
      clearTimeout(this.saveTimer);
      this.saveTimer = null;
    }
    const entries: Record<string, NoteRecord> = {};
    for (const [k, v] of notes.entries()) {
      entries[k] = v;
    }
    const payload: VaultIndexCachePayload = {
      version: CACHE_VERSION,
      generatedAt: Date.now(),
      entries,
    };
    const tmpPath = `${this.cachePath}.tmp`;
    try {
      await fs.promises.writeFile(tmpPath, JSON.stringify(payload), "utf8");
      await fs.promises.rename(tmpPath, this.cachePath);
    } catch {
      // Best-effort cache write; never block user workflow
      try {
        await fs.promises.unlink(tmpPath);
      } catch {
        // ignore
      }
    }
  }

  scheduleSave(notes: Map<string, NoteRecord>, delayMs = 800): void {
    if (this.saveTimer) {
      clearTimeout(this.saveTimer);
    }
    this.saveTimer = setTimeout(() => {
      this.saveTimer = null;
      void this.saveNow(notes);
    }, delayMs);
  }

  dispose(): void {
    if (this.saveTimer) {
      clearTimeout(this.saveTimer);
      this.saveTimer = null;
    }
  }
}
