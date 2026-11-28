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
  NoteItemDTO,
  WorkbenchBootstrapDTO,
  WorkbenchProjectItemDTO,
  WorkDTO,
} from "./server/types";
import { findHeadingLine, serializeNewNote, slugifyHeading } from "./vault/noteModel";
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
  private _noteItems: NoteItemDTO[] = [];
  private _activeProject: WorkbenchProjectItemDTO | null = null;
  private _online = false;
  private _lastServerError: string | null = null;
  private _treeProjectFilter = false;
  private _lastActiveVaultNoteFname: string | null = null;

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

  get noteItems(): NoteItemDTO[] {
    return this._noteItems;
  }

  /** Find a cached cloud Story Bible NoteItem matching title or slug (case-insensitive). */
  findNoteItem(target: string): NoteItemDTO | undefined {
    const q = target.trim().toLowerCase();
    if (!q) return undefined;
    const lastSeg = q.includes(".") ? q.split(".").pop() || q : q;
    return this._noteItems.find((ni) => {
      const t = (ni.title || "").trim().toLowerCase();
      const s = (ni.slug || "").trim().toLowerCase();
      return t === q || s === q || t === lastSeg || s === lastSeg;
    });
  }

  async togglePinWork(workId: number): Promise<boolean> {
    const pinned = await this.registry.togglePinnedWork(workId);
    this._onDidContextChange.fire();
    return pinned;
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

  get lastActiveVaultNoteFname(): string | null {
    return this._lastActiveVaultNoteFname;
  }

  setLastActiveVaultNoteFname(fname: string | null): void {
    this._lastActiveVaultNoteFname = fname;
  }

  /** Convert an absolute filesystem path to a vault note fname if it lives inside active notesDir. */
  getNoteFnameForPath(fsPath: string): string | undefined {
    const index = this._vaultIndex;
    if (!index || !fsPath) return undefined;
    if (
      path.dirname(path.resolve(fsPath)).toLowerCase() !==
      path.resolve(index.notesDir).toLowerCase()
    ) {
      return undefined;
    }
    const base = path.basename(fsPath);
    return base.toLowerCase().endsWith(".md") ? base.slice(0, -3) : undefined;
  }

  /**
   * Resolve the URI of the currently focused file across Text Editor AND VS Code's native
   * custom Markdown editors (`vscode.markdown.editor`, `vscode.markdown.preview.editor`).
   */
  resolveActiveFileUri(): vscode.Uri | undefined {
    const activeEditor = vscode.window.activeTextEditor;
    if (activeEditor && activeEditor.document.uri.scheme === "file") {
      return activeEditor.document.uri;
    }

    const activeTab = vscode.window.tabGroups.activeTabGroup?.activeTab;
    if (activeTab?.input instanceof vscode.TabInputCustom) {
      if (activeTab.input.uri.scheme === "file") {
        return activeTab.input.uri;
      }
    }
    if (activeTab?.input instanceof vscode.TabInputText) {
      if (activeTab.input.uri.scheme === "file") {
        return activeTab.input.uri;
      }
    }

    return undefined;
  }

  /**
   * Resolve the backing `vscode.TextDocument` of the currently focused Markdown note,
   * whether opened in Text Editor or VS Code's native `vscode.markdown.editor` / `vscode.markdown.preview.editor`.
   */
  async resolveActiveMarkdownDocument(): Promise<vscode.TextDocument | undefined> {
    const activeEditor = vscode.window.activeTextEditor;
    if (activeEditor && activeEditor.document.languageId === "markdown") {
      return activeEditor.document;
    }

    const uri = this.resolveActiveFileUri();
    if (uri && uri.fsPath.toLowerCase().endsWith(".md")) {
      const openDoc = vscode.workspace.textDocuments.find(
        (d) => d.uri.fsPath.toLowerCase() === uri.fsPath.toLowerCase()
      );
      if (openDoc) return openDoc;
      try {
        return await vscode.workspace.openTextDocument(uri);
      } catch {
        return undefined;
      }
    }

    const fname = this.resolveActiveVaultNoteFname();
    const note = fname ? this._vaultIndex?.getNote(fname) : undefined;
    if (note) {
      try {
        return await vscode.workspace.openTextDocument(vscode.Uri.file(note.fsPath));
      } catch {
        return undefined;
      }
    }
    return undefined;
  }

  /**
   * Resolve the currently focused vault note fname across Text Editor, native
   * `vscode.markdown.editor`, `vscode.markdown.preview.editor`, and classic Markdown Preview tabs.
   */
  resolveActiveVaultNoteFname(): string | undefined {
    const index = this._vaultIndex;
    if (!index) return undefined;

    // 1. Active text editor or native custom editor (vscode.markdown.editor / vscode.markdown.preview.editor)
    const activeUri = this.resolveActiveFileUri();
    if (activeUri) {
      const fromUri = this.getNoteFnameForPath(activeUri.fsPath);
      if (fromUri) {
        this._lastActiveVaultNoteFname = fromUri;
        return fromUri;
      }
    }

    // 2. Classic Markdown Preview webview tab (e.g. "Preview foo.bar.md")
    const activeTab = vscode.window.tabGroups.activeTabGroup?.activeTab;
    if (activeTab?.label) {
      const previewMatch = activeTab.label.match(/^Preview\s+(.+?)\.md$/i);
      if (previewMatch) {
        const candidate = previewMatch[1].trim();
        const hit = index.getNote(candidate);
        if (hit) {
          this._lastActiveVaultNoteFname = hit.fname;
          return hit.fname;
        }
      }
    }

    // 3. Visible markdown editor in the same window (e.g. Preview to the Side)
    for (const ed of vscode.window.visibleTextEditors) {
      if (ed.document.uri.scheme === "file") {
        const fromVisible = this.getNoteFnameForPath(ed.document.uri.fsPath);
        if (fromVisible) {
          this._lastActiveVaultNoteFname = fromVisible;
          return fromVisible;
        }
      }
    }

    // 4. Fallback to last active vault note if it still exists in the vault
    if (this._lastActiveVaultNoteFname && index.getNote(this._lastActiveVaultNoteFname)) {
      return this._lastActiveVaultNoteFname;
    }

    return undefined;
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
      const [data, works, noteList] = await Promise.all([
        this.apiClient.bootstrap(today),
        this.apiClient.listWorks({ limit: 150 }).catch(() => [] as WorkDTO[]),
        this.apiClient.listNoteItems({ limit: 150 }).catch(() => ({ notes: [] as NoteItemDTO[], total: 0 })),
      ]);
      this._bootstrap = data;
      this._works = works;
      this._noteItems = noteList.notes || [];
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

  /**
   * Open an existing note or create a new Dendron-compatible note file in the active vault.
   * Uses `vscode.open` so VS Code respects the user's preferred native Markdown editor
   * (`vscode.markdown.editor`, `vscode.markdown.preview.editor`, or standard Text Editor).
   */
  async openOrCreateNote(
    fname: string,
    opts?: { anchor?: string; viewColumn?: vscode.ViewColumn; initialBody?: string; title?: string }
  ): Promise<vscode.TextDocument | undefined> {
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

    const baseUri = vscode.Uri.file(targetPath);
    const openUri = opts?.anchor
      ? baseUri.with({ fragment: slugifyHeading(opts.anchor) })
      : baseUri;

    await vscode.commands.executeCommand("vscode.open", openUri, {
      viewColumn: opts?.viewColumn,
      preview: false,
    });

    this._lastActiveVaultNoteFname = note?.fname ?? cleanFname;

    // If VS Code opened it in a plain TextEditor and an anchor was requested, scroll to the heading line
    const activeEditor = vscode.window.activeTextEditor;
    if (
      opts?.anchor &&
      activeEditor &&
      activeEditor.document.uri.fsPath.toLowerCase() === targetPath.toLowerCase()
    ) {
      const targetLine = findHeadingLine(activeEditor.document.getText(), opts.anchor);
      if (targetLine !== undefined) {
        const pos = new vscode.Position(targetLine, 0);
        activeEditor.selection = new vscode.Selection(pos, pos);
        activeEditor.revealRange(new vscode.Range(pos, pos), vscode.TextEditorRevealType.InCenter);
      }
      return activeEditor.document;
    }

    return vscode.workspace.openTextDocument(baseUri);
  }

  /** Open or create daily journal for a given date (defaults to today), respecting native Markdown editor. */
  async openDailyJournal(date: Date = new Date()): Promise<vscode.TextDocument | undefined> {
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
    const uri = vscode.Uri.file(targetPath);
    await vscode.commands.executeCommand("vscode.open", uri, { preview: false });
    this._lastActiveVaultNoteFname = fname;
    return vscode.workspace.openTextDocument(uri);
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
    // Close matching open tab(s) across both Text Editor and Custom Markdown Editor tabs before trashing
    for (const group of vscode.window.tabGroups.all) {
      for (const tab of group.tabs) {
        const tabUri =
          tab.input instanceof vscode.TabInputText || tab.input instanceof vscode.TabInputCustom
            ? tab.input.uri
            : undefined;
        if (tabUri && tabUri.fsPath.toLowerCase() === note.fsPath.toLowerCase()) {
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
