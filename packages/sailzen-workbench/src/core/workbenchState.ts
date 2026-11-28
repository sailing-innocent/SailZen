import * as fs from "fs";
import * as path from "path";
import * as vscode from "vscode";
import {
  looksLikeVaultDir,
  MachineRegistry,
  resolveVaultNotesDir,
  VaultRole,
} from "./machine/machineConfig";
import { PrivacyGuard } from "./machine/privacyGuard";
import { SailZenApiClient, ServerOfflineError } from "./server/apiClient";
import {
  WorkbenchBootstrapDTO,
  WorkbenchProjectItemDTO,
  WorkDTO,
} from "./server/types";
import { serializeNewNote } from "./vault/noteModel";
import { buildDailyJournalContent, formatIsoDate } from "./vault/templateEngine";
import { RefactorPlan, VaultIndex } from "./vault/vaultIndex";

export class WorkbenchState implements vscode.Disposable {
  public readonly registry: MachineRegistry;
  public readonly privacyGuard: PrivacyGuard;
  public readonly apiClient: SailZenApiClient;

  private _vaultIndex: VaultIndex | null = null;
  private _activeVaultRoot: string | null = null;
  private _activeVaultRole: VaultRole = "private";
  private _bootstrap: WorkbenchBootstrapDTO | null = null;
  private _works: WorkDTO[] = [];
  private _activeProject: WorkbenchProjectItemDTO | null = null;
  private _online = false;
  private _lastServerError: string | null = null;
  private _treeProjectFilter = false;

  private watcher: vscode.FileSystemWatcher | null = null;
  private refreshTimer: NodeJS.Timeout | null = null;

  private readonly _onDidVaultChange = new vscode.EventEmitter<void>();
  public readonly onDidVaultChange = this._onDidVaultChange.event;

  private readonly _onDidServerDataChange = new vscode.EventEmitter<void>();
  public readonly onDidServerDataChange = this._onDidServerDataChange.event;

  private readonly _onDidContextChange = new vscode.EventEmitter<void>();
  public readonly onDidContextChange = this._onDidContextChange.event;

  constructor(private readonly output: vscode.OutputChannel) {
    this.registry = new MachineRegistry();
    this.privacyGuard = new PrivacyGuard(this.registry);
    this.apiClient = new SailZenApiClient(this.registry, this.privacyGuard);
  }

  get vaultIndex(): VaultIndex | null {
    return this._vaultIndex;
  }

  get activeVaultRoot(): string | null {
    return this._activeVaultRoot;
  }

  get activeVaultRole(): VaultRole {
    return this._activeVaultRole;
  }

  get bootstrapData(): WorkbenchBootstrapDTO | null {
    return this._bootstrap;
  }

  get works(): WorkDTO[] {
    return this._works;
  }

  get activeProject(): WorkbenchProjectItemDTO | null {
    return this._activeProject;
  }

  get isOnline(): boolean {
    return this._online;
  }

  get lastServerError(): string | null {
    return this._lastServerError;
  }

  get treeProjectFilter(): boolean {
    return this._treeProjectFilter;
  }

  toggleTreeProjectFilter(): boolean {
    this._treeProjectFilter = !this._treeProjectFilter;
    this._onDidVaultChange.fire();
    this._onDidContextChange.fire();
    return this._treeProjectFilter;
  }

  /** Reload ~/.sailzen/machine.json merged with VS Code configuration. */
  reloadConfig(): void {
    const cfg = vscode.workspace.getConfiguration("sailzen");
    this.registry.load({
      serverUrl: cfg.get<string>("server.baseUrl"),
      apiToken: cfg.get<string>("server.apiToken"),
      privateVaultPath: cfg.get<string>("vault.privatePath"),
      workVaultPath: cfg.get<string>("vault.workPath"),
    });
  }

  /** Fast startup: load config, resolve vault (warm cache first), then background refresh server. */
  async initialize(): Promise<void> {
    this.reloadConfig();

    await this.detectAndLoadVault();

    // Refresh Rhythm/Projects asynchronously without blocking extension startup
    void this.refreshServerData();

    const intervalMins = vscode.workspace
      .getConfiguration("sailzen")
      .get<number>("rhythm.autoRefreshMinutes", 5);
    if (intervalMins > 0) {
      this.refreshTimer = setInterval(() => {
        void this.refreshServerData();
      }, intervalMins * 60 * 1000);
    }
  }

  /** Detect active vault from open workspace folders or ~/.sailzen/machine.json. */
  async detectAndLoadVault(forcedRole?: VaultRole): Promise<void> {
    const folders = vscode.workspace.workspaceFolders || [];
    let resolvedRoot: string | null = null;
    let role: VaultRole = forcedRole ?? this.registry.getActiveVaultRole();

    if (!forcedRole) {
      // Check if an opened workspace folder IS one of the configured vaults or looks like a vault
      for (const f of folders) {
        const fp = f.uri.fsPath;
        const zone = this.privacyGuard.classifyPath(fp);
        if (zone === "WORK_VAULT") {
          resolvedRoot = this.registry.getVaultSlot("work")!.path;
          role = "work";
          break;
        }
        if (zone === "PRIVATE_VAULT") {
          resolvedRoot = this.registry.getVaultSlot("private")!.path;
          role = "private";
          break;
        }
        if (looksLikeVaultDir(fp)) {
          resolvedRoot = fp;
          break;
        }
      }
    }

    if (!resolvedRoot) {
      const slot = this.registry.getVaultSlot(role);
      if (slot?.path && fs.existsSync(slot.path)) {
        resolvedRoot = slot.path;
      } else {
        // Fallback: check the other slot or standard D:/vault on personal machine
        const otherRole: VaultRole = role === "private" ? "work" : "private";
        const other = this.registry.getVaultSlot(otherRole);
        if (other?.path && fs.existsSync(other.path)) {
          resolvedRoot = other.path;
          role = otherRole;
        } else if (fs.existsSync("D:/vault") && looksLikeVaultDir("D:/vault")) {
          resolvedRoot = "D:/vault";
          role = "private";
        }
      }
    }

    this._activeVaultRole = role;
    this._activeVaultRoot = resolvedRoot;

    this.disposeVaultWatcher();
    if (this._vaultIndex) {
      this._vaultIndex.dispose();
      this._vaultIndex = null;
    }

    if (!resolvedRoot) {
      this.output.appendLine("[Vault] No vault configured yet.");
      this._onDidVaultChange.fire();
      this._onDidContextChange.fire();
      return;
    }

    const slot = this.registry.getVaultSlot(role);
    const notesDir = resolveVaultNotesDir(resolvedRoot, slot?.notesDir || "notes");
    const index = new VaultIndex(notesDir);
    this._vaultIndex = index;

    // Stage 1: Instant warm load from cache (~30ms)
    const cachedCount = await index.loadFromCacheOnly();
    if (cachedCount > 0) {
      this.output.appendLine(`[Vault] Warm-loaded ${cachedCount} notes from cache (${notesDir})`);
      this._onDidVaultChange.fire();
      this._onDidContextChange.fire();
    }

    // Stage 2: Live incremental file watcher (active immediately)
    const pattern = new vscode.RelativePattern(notesDir, "*.md");
    this.watcher = vscode.workspace.createFileSystemWatcher(pattern);
    this.watcher.onDidCreate(async (uri) => {
      await index.upsertFile(uri.fsPath);
      this._onDidVaultChange.fire();
    });
    this.watcher.onDidChange(async (uri) => {
      await index.upsertFile(uri.fsPath);
      this._onDidVaultChange.fire();
    });
    this.watcher.onDidDelete((uri) => {
      index.removeFile(uri.fsPath);
      this._onDidVaultChange.fire();
    });

    // Stage 3: Incremental disk verification (non-blocking when cache is warm)
    const syncTask = index.syncFromDisk(true).then((stats) => {
      this.output.appendLine(
        `[Vault] Synced ${stats.totalNotes} notes in ${stats.durationMs}ms (cacheHits=${stats.cacheHits}, parsed=${stats.parsedFiles})`
      );
      this._onDidVaultChange.fire();
      this._onDidContextChange.fire();
    });
    if (cachedCount === 0) {
      // Cold first run without cache: kick off in background too so VS Code UI never stalls
      void syncTask;
    } else {
      void syncTask;
    }
  }

  async reloadVaultFull(): Promise<void> {
    if (!this._vaultIndex) {
      await this.detectAndLoadVault();
      return;
    }
    const stats = await this._vaultIndex.syncFromDisk(false);
    await this._vaultIndex.flushCache();
    this.output.appendLine(`[Vault] Full reload: ${stats.totalNotes} notes in ${stats.durationMs}ms`);
    this._onDidVaultChange.fire();
  }

  async switchVault(role: VaultRole): Promise<void> {
    await this.registry.setActiveVaultRole(role);
    await this.detectAndLoadVault(role);
    if (this.privacyGuard.isWorkOfflineActive()) {
      this._bootstrap = null;
      this._online = false;
      this._onDidServerDataChange.fire();
    } else {
      void this.refreshServerData();
    }
  }

  async refreshServerData(): Promise<void> {
    this.reloadConfig();
    if (this.privacyGuard.isWorkOfflineActive()) {
      this._online = false;
      this._lastServerError = "Work Vault offline isolation active";
      this._onDidServerDataChange.fire();
      this._onDidContextChange.fire();
      return;
    }

    try {
      const today = formatIsoDate(new Date());
      const [data, works] = await Promise.all([
        this.apiClient.bootstrap(today),
        this.apiClient.listWorks({ limit: 80 }).catch(() => [] as WorkDTO[]),
      ]);
      this._bootstrap = data;
      this._works = works;
      this._online = true;
      this._lastServerError = null;
      this.resolveActiveProject();
    } catch (err) {
      this._online = false;
      this._lastServerError =
        err instanceof ServerOfflineError || err instanceof Error
          ? err.message
          : String(err);
      this.output.appendLine(`[Server] Refresh failed: ${this._lastServerError}`);
    }
    this._onDidServerDataChange.fire();
    this._onDidContextChange.fire();
  }

  /** Match current VS Code workspace folder against cloud Ventures via local machine bindings or repo_hints. */
  resolveActiveProject(): WorkbenchProjectItemDTO | null {
    const projects = this._bootstrap?.projects || [];
    if (projects.length === 0) {
      this._activeProject = null;
      return null;
    }

    const folders = vscode.workspace.workspaceFolders || [];
    for (const f of folders) {
      const fp = f.uri.fsPath;
      // 1. Exact local binding in ~/.sailzen/machine.json or .sailzen-project.json
      const boundSlug = this.registry.findProjectSlugForFolder(fp);
      if (boundSlug) {
        const hit = projects.find((p) => p.workbench.slug === boundSlug);
        if (hit) {
          this._activeProject = hit;
          return hit;
        }
      }
      // 2. Folder basename matches semantic repo_hints or slug
      const base = path.basename(fp).toLowerCase();
      const hintHit = projects.find(
        (p) =>
          p.workbench.slug === base ||
          p.workbench.repo_hints.some((h) => h.toLowerCase().endsWith(base))
      );
      if (hintHit) {
        this._activeProject = hintHit;
        return hintHit;
      }
    }

    this._activeProject = null;
    return null;
  }

  /** Open an existing note or create a new Dendron-compatible note file in the active vault. */
  async openOrCreateNote(
    fname: string,
    opts?: { anchor?: string; viewColumn?: vscode.ViewColumn; initialBody?: string; title?: string }
  ): Promise<vscode.TextEditor | undefined> {
    if (!this._vaultIndex) {
      vscode.window.showWarningMessage("SailZen: No active vault found. Configure ~/.sailzen/machine.json first.");
      return undefined;
    }
    const cleanFname = fname.trim().replace(/\.md$/i, "");
    if (!cleanFname) return undefined;

    let note = this._vaultIndex.getNote(cleanFname);
    let targetPath: string;

    if (note) {
      targetPath = note.fsPath;
    } else {
      targetPath = path.join(this._vaultIndex.notesDir, `${cleanFname}.md`);
      if (!fs.existsSync(targetPath)) {
        const content = serializeNewNote({
          fname: cleanFname,
          title: opts?.title,
          body: opts?.initialBody,
        });
        await fs.promises.writeFile(targetPath, content, "utf8");
      }
      await this._vaultIndex.upsertFile(targetPath);
      this._onDidVaultChange.fire();
    }

    const doc = await vscode.workspace.openTextDocument(vscode.Uri.file(targetPath));
    const editor = await vscode.window.showTextDocument(doc, {
      viewColumn: opts?.viewColumn,
      preview: false,
    });

    if (opts?.anchor) {
      const headingSlug = opts.anchor.toLowerCase().replace(/[^a-z0-9\u4e00-\u9fff]+/g, "-");
      for (let line = 0; line < doc.lineCount; line++) {
        const text = doc.lineAt(line).text;
        if (/^#{1,6}\s+/.test(text)) {
          const slug = text
            .replace(/^#{1,6}\s+/, "")
            .trim()
            .toLowerCase()
            .replace(/[^a-z0-9\u4e00-\u9fff]+/g, "-");
          if (slug === headingSlug || text.toLowerCase().includes(opts.anchor.toLowerCase())) {
            const pos = new vscode.Position(line, 0);
            editor.selection = new vscode.Selection(pos, pos);
            editor.revealRange(new vscode.Range(pos, pos), vscode.TextEditorRevealType.InCenter);
            break;
          }
        }
      }
    }

    return editor;
  }

  /** Open or create daily journal for a given date (defaults to today). */
  async openDailyJournal(date: Date = new Date()): Promise<vscode.TextEditor | undefined> {
    if (!this._vaultIndex) {
      vscode.window.showWarningMessage("SailZen: No active vault configured.");
      return undefined;
    }
    const { fname, content } = await buildDailyJournalContent(this._vaultIndex.notesDir, date);
    const targetPath = path.join(this._vaultIndex.notesDir, `${fname}.md`);
    if (!fs.existsSync(targetPath)) {
      await fs.promises.writeFile(targetPath, content, "utf8");
      await this._vaultIndex.upsertFile(targetPath);
      this._onDidVaultChange.fire();
    }
    const doc = await vscode.workspace.openTextDocument(vscode.Uri.file(targetPath));
    return vscode.window.showTextDocument(doc, { preview: false });
  }

  /**
   * Apply a RefactorPlan atomically via vscode.WorkspaceEdit (supports Undo & dirty open buffers!).
   */
  async applyRefactorPlan(plan: RefactorPlan): Promise<boolean> {
    const wsEdit = new vscode.WorkspaceEdit();

    // 1. Apply wikilink text edits using accurate Document positions
    const editsByFile = new Map<string, typeof plan.textEdits>();
    for (const edit of plan.textEdits) {
      const list = editsByFile.get(edit.fsPath) ?? [];
      list.push(edit);
      editsByFile.set(edit.fsPath, list);
    }

    for (const [fsPath, edits] of editsByFile.entries()) {
      const uri = vscode.Uri.file(fsPath);
      const doc = await vscode.workspace.openTextDocument(uri);
      for (const e of edits) {
        const range = new vscode.Range(
          doc.positionAt(e.start),
          doc.positionAt(e.end)
        );
        wsEdit.replace(uri, range, e.newText);
      }
    }

    // 2. Rename backing markdown files
    for (const op of plan.fileRenames) {
      wsEdit.renameFile(
        vscode.Uri.file(op.oldFsPath),
        vscode.Uri.file(op.newFsPath),
        { overwrite: false }
      );
    }

    const applied = await vscode.workspace.applyEdit(wsEdit);
    if (applied) {
      // Save modified referencing files so disk & Git stay clean
      await vscode.workspace.saveAll(false);
      await this.reloadVaultFull();
    }
    return applied;
  }

  /** Delete a note safely to OS Trash and remove it from the in-memory index. */
  async deleteNoteToTrash(fname: string): Promise<boolean> {
    if (!this._vaultIndex) return false;
    const note = this._vaultIndex.getNote(fname);
    if (!note) return false;

    const uri = vscode.Uri.file(note.fsPath);
    // Close matching open tab(s) cleanly before trashing
    for (const group of vscode.window.tabGroups.all) {
      for (const tab of group.tabs) {
        if (
          tab.input instanceof vscode.TabInputText &&
          tab.input.uri.fsPath.toLowerCase() === note.fsPath.toLowerCase()
        ) {
          await vscode.window.tabGroups.close(tab);
        }
      }
    }

    await vscode.workspace.fs.delete(uri, { useTrash: true });
    this._vaultIndex.removeFile(note.fsPath);
    this._onDidVaultChange.fire();
    return true;
  }

  private disposeVaultWatcher(): void {
    if (this.watcher) {
      this.watcher.dispose();
      this.watcher = null;
    }
  }

  dispose(): void {
    this.disposeVaultWatcher();
    if (this.refreshTimer) {
      clearInterval(this.refreshTimer);
      this.refreshTimer = null;
    }
    this._vaultIndex?.dispose();
    this._onDidVaultChange.dispose();
    this._onDidServerDataChange.dispose();
    this._onDidContextChange.dispose();
  }
}
