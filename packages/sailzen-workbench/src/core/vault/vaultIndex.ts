import * as fs from "fs";
import * as path from "path";
import { VaultCacheStore } from "./cacheStore";
import {
  buildNoteRecord,
  deriveTitleFromFname,
  extractWikilinks,
  NoteRecord,
} from "./noteModel";

export interface HierarchyChildItem {
  /** Full dot-separated fname or virtual stub prefix */
  fname: string;
  /** Short display segment (last part after '.') */
  segment: string;
  /** Real NoteRecord if a backing .md file exists; undefined for virtual stub nodes */
  note?: NoteRecord;
  /** Whether this node has children below it */
  hasChildren: boolean;
}

export interface SearchMatch {
  note: NoteRecord;
  score: number;
}

export interface TextEditSpan {
  fsPath: string;
  fname: string;
  start: number;
  end: number;
  oldText: string;
  newText: string;
}

export interface FileRenameOp {
  oldFname: string;
  newFname: string;
  oldFsPath: string;
  newFsPath: string;
}

export interface RefactorPlan {
  fileRenames: FileRenameOp[];
  textEdits: TextEditSpan[];
  affectedReferencingFiles: number;
}

export interface VaultIndexStats {
  totalNotes: number;
  cacheHits: number;
  parsedFiles: number;
  durationMs: number;
}

const READ_CONCURRENCY = 64;

/** Run an async mapper over items with bounded concurrency. */
async function mapConcurrent<T>(
  items: T[],
  limit: number,
  fn: (item: T) => Promise<void>
): Promise<void> {
  if (items.length === 0) return;
  let cursor = 0;
  const workers = Array.from({ length: Math.min(limit, items.length) }, async () => {
    while (cursor < items.length) {
      const idx = cursor++;
      await fn(items[idx]);
    }
  });
  await Promise.all(workers);
}

/**
 * Pure-Node ultra-fast in-memory dot-hierarchy index for Dendron-format vaults.
 * Zero Prisma, zero Express, zero VS Code runtime dependency (100% unit-testable).
 */
export class VaultIndex {
  public readonly notesDir: string;
  private readonly cacheStore: VaultCacheStore;

  /** key = fname.toLowerCase() */
  private notes = new Map<string, NoteRecord>();
  /** key = note.id */
  private byId = new Map<string, NoteRecord>();
  /** key = targetFname.toLowerCase() -> Set of sourceFname.toLowerCase() */
  private backlinks = new Map<string, Set<string>>();
  /** key = parentPrefix.toLowerCase() ("" for root) -> Set of direct child keys (lowercase) */
  private childrenMap = new Map<string, Set<string>>();
  /** Preserve canonical casing for virtual/stub prefixes */
  private canonicalPrefix = new Map<string, string>();

  private lastStats: VaultIndexStats = {
    totalNotes: 0,
    cacheHits: 0,
    parsedFiles: 0,
    durationMs: 0,
  };

  constructor(notesDir: string) {
    this.notesDir = notesDir;
    this.cacheStore = new VaultCacheStore(notesDir);
  }

  get stats(): VaultIndexStats {
    return this.lastStats;
  }

  get size(): number {
    return this.notes.size;
  }

  /** Fast warm load from cache only (no disk scan), for instant UI startup. */
  async loadFromCacheOnly(): Promise<number> {
    const cached = await this.cacheStore.load();
    if (cached.size === 0) return 0;
    this.notes = cached;
    this.rebuildDerivedIndexes();
    return this.notes.size;
  }

  /**
   * Full incremental sync against `notesDir`:
   * reuses cached entries whose (mtimeMs, size) match, parses only new/modified .md files.
   */
  async syncFromDisk(useExistingCache = true): Promise<VaultIndexStats> {
    const t0 = Date.now();
    const cached = useExistingCache ? await this.cacheStore.load() : new Map<string, NoteRecord>();

    let dirEntries: fs.Dirent[];
    try {
      dirEntries = await fs.promises.readdir(this.notesDir, { withFileTypes: true });
    } catch {
      this.notes.clear();
      this.rebuildDerivedIndexes();
      this.lastStats = { totalNotes: 0, cacheHits: 0, parsedFiles: 0, durationMs: Date.now() - t0 };
      return this.lastStats;
    }

    const mdNames = dirEntries
      .filter((d) => d.isFile() && d.name.toLowerCase().endsWith(".md"))
      .map((d) => d.name);

    const nextNotes = new Map<string, NoteRecord>();
    let cacheHits = 0;
    let parsedFiles = 0;

    await mapConcurrent(mdNames, READ_CONCURRENCY, async (fileName) => {
      const fname = fileName.slice(0, -3);
      const key = fname.toLowerCase();
      const fsPath = path.join(this.notesDir, fileName);

      let st: fs.Stats;
      try {
        st = await fs.promises.stat(fsPath);
      } catch {
        return;
      }

      const prev = cached.get(key);
      if (
        prev &&
        prev.mtimeMs === st.mtimeMs &&
        prev.size === st.size &&
        prev.fsPath === fsPath
      ) {
        nextNotes.set(key, prev);
        cacheHits++;
        return;
      }

      try {
        const raw = await fs.promises.readFile(fsPath, "utf8");
        const rec = buildNoteRecord(fname, fsPath, raw, st.mtimeMs, st.size);
        nextNotes.set(key, rec);
        parsedFiles++;
      } catch {
        // Ignore transient unreadable file
      }
    });

    this.notes = nextNotes;
    this.rebuildDerivedIndexes();

    const durationMs = Date.now() - t0;
    this.lastStats = {
      totalNotes: this.notes.size,
      cacheHits,
      parsedFiles,
      durationMs,
    };

    if (parsedFiles > 0 || cached.size !== this.notes.size) {
      this.cacheStore.scheduleSave(this.notes, 500);
    }

    return this.lastStats;
  }

  /** Incrementally index or update a single markdown file. */
  async upsertFile(fsPath: string): Promise<NoteRecord | null> {
    if (!fsPath.toLowerCase().endsWith(".md")) return null;
    if (path.dirname(path.resolve(fsPath)).toLowerCase() !== path.resolve(this.notesDir).toLowerCase()) {
      return null;
    }

    const fileName = path.basename(fsPath);
    const fname = fileName.slice(0, -3);
    const key = fname.toLowerCase();

    try {
      const [st, raw] = await Promise.all([
        fs.promises.stat(fsPath),
        fs.promises.readFile(fsPath, "utf8"),
      ]);
      const prev = this.notes.get(key);
      const rec = buildNoteRecord(fname, fsPath, raw, st.mtimeMs, st.size);

      // Update backlinks incrementally
      if (prev) {
        for (const oldTarget of prev.links) {
          this.backlinks.get(oldTarget)?.delete(key);
        }
        if (prev.id) this.byId.delete(prev.id);
      }

      this.notes.set(key, rec);
      if (rec.id) this.byId.set(rec.id, rec);
      for (const target of rec.links) {
        let set = this.backlinks.get(target);
        if (!set) {
          set = new Set();
          this.backlinks.set(target, set);
        }
        set.add(key);
      }
      this.registerHierarchyPath(rec.fname);
      this.cacheStore.scheduleSave(this.notes);
      return rec;
    } catch {
      return null;
    }
  }

  /** Remove a deleted markdown file from memory index. */
  removeFile(fsPath: string): boolean {
    const fileName = path.basename(fsPath);
    if (!fileName.toLowerCase().endsWith(".md")) return false;
    const fname = fileName.slice(0, -3);
    const key = fname.toLowerCase();
    const prev = this.notes.get(key);
    if (!prev) return false;

    this.notes.delete(key);
    this.rebuildDerivedIndexes();
    this.cacheStore.scheduleSave(this.notes);
    return true;
  }

  getNote(fname: string): NoteRecord | undefined {
    return this.notes.get(fname.toLowerCase());
  }

  getNoteById(id: string): NoteRecord | undefined {
    return this.byId.get(id);
  }

  getAllNotes(): NoteRecord[] {
    return Array.from(this.notes.values());
  }

  /** Get all notes referencing `targetFname` via [[wikilink]]. */
  getReferencingNotes(targetFname: string): NoteRecord[] {
    const set = this.backlinks.get(targetFname.toLowerCase());
    if (!set) return [];
    const out: NoteRecord[] = [];
    for (const srcKey of set) {
      const rec = this.notes.get(srcKey);
      if (rec) out.push(rec);
    }
    return out;
  }

  /** Direct children of a dot-hierarchy prefix ("" for root domains). */
  getChildren(parentPrefix = ""): HierarchyChildItem[] {
    const key = parentPrefix.toLowerCase();
    const childKeys = this.childrenMap.get(key);
    if (!childKeys || childKeys.size === 0) return [];

    const items: HierarchyChildItem[] = [];
    for (const childKey of childKeys) {
      const note = this.notes.get(childKey);
      const fname = note ? note.fname : (this.canonicalPrefix.get(childKey) ?? childKey);
      const parts = fname.split(".");
      const segment = parts[parts.length - 1];
      const grandchildren = this.childrenMap.get(childKey);
      items.push({
        fname,
        segment,
        note,
        hasChildren: Boolean(grandchildren && grandchildren.size > 0),
      });
    }

    items.sort((a, b) => a.segment.localeCompare(b.segment, undefined, { numeric: true }));
    return items;
  }

  /** Return all existing daily journal day numbers for a given (year, month 1..12). */
  getDailyJournalDays(year: number, month: number): Map<number, NoteRecord> {
    const prefix = `journal.daily.${year}.${String(month).padStart(2, "0")}.`;
    const result = new Map<number, NoteRecord>();
    for (const [k, rec] of this.notes.entries()) {
      if (k.startsWith(prefix)) {
        const rest = k.slice(prefix.length);
        if (/^\d{2}$/.test(rest)) {
          result.set(Number(rest), rec);
        }
      }
    }
    return result;
  }

  /**
   * Fast dot-hierarchy fuzzy search for QuickPick Lookup & Wikilink Completion.
   * Empty query returns recently updated notes.
   */
  search(query: string, limit = 50, namespacePrefix?: string): SearchMatch[] {
    const q = query.trim().toLowerCase();
    const ns = namespacePrefix?.trim().toLowerCase();
    const matches: SearchMatch[] = [];

    if (!q) {
      for (const note of this.notes.values()) {
        if (ns && !note.fname.toLowerCase().startsWith(ns)) continue;
        matches.push({ note, score: note.updated || note.mtimeMs });
      }
      matches.sort((a, b) => b.score - a.score);
      return matches.slice(0, limit);
    }

    const tokens = q.split(/[\s.]+/).filter(Boolean);

    for (const note of this.notes.values()) {
      const fnLower = note.fname.toLowerCase();
      if (ns && !fnLower.startsWith(ns)) continue;
      const titleLower = note.title.toLowerCase();

      let score = 0;
      if (fnLower === q) {
        score = 10000;
      } else if (fnLower.startsWith(q)) {
        score = 5000 - Math.min(fnLower.length, 500);
      } else if (fnLower.includes(q)) {
        score = 3000 - fnLower.indexOf(q);
      } else if (titleLower.includes(q)) {
        score = 2200 - titleLower.indexOf(q);
      } else if (tokens.length > 1 && tokens.every((t) => fnLower.includes(t) || titleLower.includes(t))) {
        score = 1500;
      } else {
        // Lightweight subsequence match on fname
        let ti = 0;
        for (let fi = 0; fi < fnLower.length && ti < q.length; fi++) {
          if (fnLower[fi] === q[ti]) ti++;
        }
        if (ti === q.length) {
          score = 500 - Math.min(fnLower.length, 400);
        }
      }

      if (score > 0) {
        // Mild recency boost
        const recencyBoost = Math.min(200, Math.floor((note.mtimeMs || 0) / 1e11));
        matches.push({ note, score: score + recencyBoost });
      }
    }

    matches.sort((a, b) => b.score - a.score || a.note.fname.localeCompare(b.note.fname));
    return matches.slice(0, limit);
  }

  /**
   * Plan an atomic single-note rename with full cross-vault wikilink updates.
   * Pure computation — caller applies via vscode.WorkspaceEdit (undoable & dirty-safe) or fs.
   */
  async planRename(oldFname: string, newFname: string): Promise<RefactorPlan> {
    const existing = this.getNote(oldFname);
    if (!existing) {
      throw new Error(`Note not found: ${oldFname}`);
    }
    if (oldFname.toLowerCase() === newFname.toLowerCase()) {
      return { fileRenames: [], textEdits: [], affectedReferencingFiles: 0 };
    }
    if (this.getNote(newFname)) {
      throw new Error(`Target note already exists: ${newFname}`);
    }

    const renameMap = new Map<string, string>([[existing.fname.toLowerCase(), newFname]]);
    const fileRenames: FileRenameOp[] = [
      {
        oldFname: existing.fname,
        newFname,
        oldFsPath: existing.fsPath,
        newFsPath: path.join(this.notesDir, `${newFname}.md`),
      },
    ];

    return this.buildLinkEditsForRenames(fileRenames, renameMap);
  }

  /**
   * Plan an atomic hierarchy refactor (renames `oldPrefix` and all `oldPrefix.*` descendants
   * to `newPrefix` / `newPrefix.*`, and updates every wikilink across the entire vault).
   */
  async planRefactorHierarchy(oldPrefix: string, newPrefix: string): Promise<RefactorPlan> {
    const oldLower = oldPrefix.toLowerCase();
    if (oldLower === newPrefix.toLowerCase()) {
      return { fileRenames: [], textEdits: [], affectedReferencingFiles: 0 };
    }

    const matched: NoteRecord[] = [];
    for (const note of this.notes.values()) {
      const key = note.fname.toLowerCase();
      if (key === oldLower || key.startsWith(`${oldLower}.`)) {
        matched.push(note);
      }
    }
    if (matched.length === 0) {
      throw new Error(`No notes matched hierarchy prefix: ${oldPrefix}`);
    }

    const fileRenames: FileRenameOp[] = [];
    const renameMap = new Map<string, string>();
    for (const note of matched) {
      const suffix = note.fname.slice(oldPrefix.length);
      const targetFname = `${newPrefix}${suffix}`;
      if (this.getNote(targetFname) && !matched.some((m) => m.fname.toLowerCase() === targetFname.toLowerCase())) {
        throw new Error(`Target note already exists: ${targetFname}`);
      }
      fileRenames.push({
        oldFname: note.fname,
        newFname: targetFname,
        oldFsPath: note.fsPath,
        newFsPath: path.join(this.notesDir, `${targetFname}.md`),
      });
      renameMap.set(note.fname.toLowerCase(), targetFname);
    }

    return this.buildLinkEditsForRenames(fileRenames, renameMap);
  }

  /** Apply a RefactorPlan directly to disk (used in CLI/tests; VS Code uses WorkspaceEdit). */
  async applyRefactorPlanToDisk(plan: RefactorPlan): Promise<void> {
    // 1. Group edits by fsPath and apply in reverse offset order
    const editsByFile = new Map<string, TextEditSpan[]>();
    for (const edit of plan.textEdits) {
      const list = editsByFile.get(edit.fsPath) ?? [];
      list.push(edit);
      editsByFile.set(edit.fsPath, list);
    }

    for (const [fsPath, edits] of editsByFile.entries()) {
      let content = await fs.promises.readFile(fsPath, "utf8");
      const sorted = [...edits].sort((a, b) => b.start - a.start);
      for (const e of sorted) {
        content = content.slice(0, e.start) + e.newText + content.slice(e.end);
      }
      await fs.promises.writeFile(fsPath, content, "utf8");
    }

    // 2. Rename files
    for (const op of plan.fileRenames) {
      await fs.promises.rename(op.oldFsPath, op.newFsPath);
    }

    // 3. Refresh index
    await this.syncFromDisk(false);
  }

  async flushCache(): Promise<void> {
    await this.cacheStore.saveNow(this.notes);
  }

  dispose(): void {
    this.cacheStore.dispose();
  }

  // --------------------------------------------------------------------------
  // Internal helpers
  // --------------------------------------------------------------------------

  private async buildLinkEditsForRenames(
    fileRenames: FileRenameOp[],
    renameMap: Map<string, string>
  ): Promise<RefactorPlan> {
    const candidateFiles = new Set<NoteRecord>();
    for (const oldKey of renameMap.keys()) {
      for (const refNote of this.getReferencingNotes(oldKey)) {
        candidateFiles.add(refNote);
      }
    }

    const textEdits: TextEditSpan[] = [];
    const affectedFiles = new Set<string>();

    for (const refNote of candidateFiles) {
      let raw: string;
      try {
        raw = await fs.promises.readFile(refNote.fsPath, "utf8");
      } catch {
        continue;
      }

      const links = extractWikilinks(raw, 0);
      for (const link of links) {
        const mapped = renameMap.get(link.target.toLowerCase());
        if (mapped) {
          textEdits.push({
            fsPath: refNote.fsPath,
            fname: refNote.fname,
            start: link.targetStart,
            end: link.targetEnd,
            oldText: link.target,
            newText: mapped,
          });
          affectedFiles.add(refNote.fsPath);
        }
      }
    }

    return {
      fileRenames,
      textEdits,
      affectedReferencingFiles: affectedFiles.size,
    };
  }

  private rebuildDerivedIndexes(): void {
    this.byId.clear();
    this.backlinks.clear();
    this.childrenMap.clear();
    this.canonicalPrefix.clear();

    for (const [key, rec] of this.notes.entries()) {
      if (rec.id) this.byId.set(rec.id, rec);
      for (const target of rec.links) {
        let set = this.backlinks.get(target);
        if (!set) {
          set = new Set();
          this.backlinks.set(target, set);
        }
        set.add(key);
      }
      this.registerHierarchyPath(rec.fname);
    }
  }

  private registerHierarchyPath(fname: string): void {
    const parts = fname.split(".");
    let parentKey = "";
    let built = "";
    for (let i = 0; i < parts.length; i++) {
      built = i === 0 ? parts[i] : `${built}.${parts[i]}`;
      const childKey = built.toLowerCase();
      if (!this.canonicalPrefix.has(childKey)) {
        this.canonicalPrefix.set(childKey, built);
      }
      let children = this.childrenMap.get(parentKey);
      if (!children) {
        children = new Set();
        this.childrenMap.set(parentKey, children);
      }
      children.add(childKey);
      parentKey = childKey;
    }
  }
}

export { deriveTitleFromFname };
