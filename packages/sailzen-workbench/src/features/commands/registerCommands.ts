import * as fs from "fs";
import * as path from "path";
import * as vscode from "vscode";
import { PrivacyViolationError } from "../../core/machine/privacyGuard";
import { BlockStatus, TimeBlockDTO, WorkbenchProjectItemDTO } from "../../core/server/types";
import { WorkbenchState } from "../../core/workbenchState";
import {
  formatRhythmSnapshotMarkdown,
  injectRhythmFencedSection,
} from "../editor/journalBridge";
import { ProjectTreeItem } from "../views/projectsView";
import { RhythmTreeItem } from "../views/rhythmView";

interface LookupQuickPickItem extends vscode.QuickPickItem {
  fname: string;
  isCreateNew?: boolean;
}

function getActiveNoteFname(state: WorkbenchState): string | undefined {
  const editor = vscode.window.activeTextEditor;
  const index = state.vaultIndex;
  if (!editor || !index) return undefined;
  const fsPath = editor.document.uri.fsPath;
  if (
    path.dirname(path.resolve(fsPath)).toLowerCase() !==
    path.resolve(index.notesDir).toLowerCase()
  ) {
    return undefined;
  }
  const base = path.basename(fsPath);
  return base.toLowerCase().endsWith(".md") ? base.slice(0, -3) : undefined;
}

export function registerWorkbenchCommands(
  context: vscode.ExtensionContext,
  state: WorkbenchState
): void {
  // 1. Lookup / Create Note (fast dot-hierarchy QuickPick)
  context.subscriptions.push(
    vscode.commands.registerCommand("sailzen.lookupNote", async (initialValue?: string) => {
      const index = state.vaultIndex;
      if (!index) {
        vscode.window.showWarningMessage("SailZen: No active vault configured.");
        return;
      }

      const qp = vscode.window.createQuickPick<LookupQuickPickItem>();
      qp.placeholder = "Type dot-hierarchy note name (e.g. dev-note.cpp.cuda or journal.daily...)";
      qp.matchOnDescription = true;
      qp.matchOnDetail = false;

      const updateItems = (rawValue: string) => {
        const q = rawValue.trim();
        const matches = index.search(q, 45);
        const items: LookupQuickPickItem[] = matches.map((m) => ({
          label: `$(markdown) ${m.note.fname}`,
          description: m.note.title !== m.note.fname ? m.note.title : "",
          fname: m.note.fname,
        }));

        if (q && !index.getNote(q)) {
          items.unshift({
            label: `$(new-file) Create New: ${q}`,
            description: "New dot-hierarchy note",
            fname: q,
            isCreateNew: true,
          });
        }
        qp.items = items;
      };

      qp.onDidChangeValue((val) => updateItems(val));
      qp.onDidAccept(async () => {
        const sel = qp.selectedItems[0];
        const target = sel ? sel.fname : qp.value.trim();
        qp.hide();
        if (target) {
          await state.openOrCreateNote(target);
        }
      });
      qp.onDidHide(() => qp.dispose());

      const initVal = typeof initialValue === "string" ? initialValue : "";
      qp.value = initVal;
      updateItems(initVal);
      qp.show();
    })
  );

  // 2. Open Today's Journal
  context.subscriptions.push(
    vscode.commands.registerCommand("sailzen.gotoToday", async () => {
      await state.openDailyJournal(new Date());
    })
  );

  // 3. Create Note
  context.subscriptions.push(
    vscode.commands.registerCommand("sailzen.createNote", async () => {
      const current = getActiveNoteFname(state);
      const defaultPrefix = current ? `${current}.` : "";
      const fname = await vscode.window.showInputBox({
        prompt: "New note dot-hierarchy name (without .md)",
        value: defaultPrefix,
        valueSelection: [defaultPrefix.length, defaultPrefix.length],
      });
      if (fname?.trim()) {
        await state.openOrCreateNote(fname.trim());
      }
    })
  );

  // 4. Rename Note (Atomic cross-vault wikilink update)
  context.subscriptions.push(
    vscode.commands.registerCommand("sailzen.renameNote", async () => {
      const index = state.vaultIndex;
      const oldFname = getActiveNoteFname(state);
      if (!index || !oldFname) {
        vscode.window.showWarningMessage("SailZen: Open a vault markdown note to rename.");
        return;
      }
      const newFname = await vscode.window.showInputBox({
        prompt: `Rename "${oldFname}" (all [[wikilinks]] across the vault will be updated)`,
        value: oldFname,
      });
      if (!newFname || newFname.trim() === oldFname) return;

      try {
        const plan = await index.planRename(oldFname, newFname.trim());
        const confirm = await vscode.window.showInformationMessage(
          `Rename "${oldFname}" → "${newFname.trim()}" and update ${plan.textEdits.length} link(s) across ${plan.affectedReferencingFiles} file(s)?`,
          { modal: true },
          "Rename"
        );
        if (confirm !== "Rename") return;
        const ok = await state.applyRefactorPlan(plan);
        if (ok) {
          vscode.window.showInformationMessage(
            `Renamed to "${newFname.trim()}" (updated ${plan.textEdits.length} links).`
          );
        }
      } catch (err) {
        vscode.window.showErrorMessage(err instanceof Error ? err.message : String(err));
      }
    })
  );

  // 5. Refactor Hierarchy (Atomic subtree rename + cross-vault link update)
  context.subscriptions.push(
    vscode.commands.registerCommand("sailzen.refactorHierarchy", async () => {
      const index = state.vaultIndex;
      if (!index) return;
      const current = getActiveNoteFname(state) || "";
      const oldPrefix = await vscode.window.showInputBox({
        prompt: "Hierarchy prefix to refactor (e.g. project.old-name)",
        value: current,
      });
      if (!oldPrefix?.trim()) return;

      const newPrefix = await vscode.window.showInputBox({
        prompt: `New hierarchy prefix for "${oldPrefix.trim()}"`,
        value: oldPrefix.trim(),
      });
      if (!newPrefix?.trim() || newPrefix.trim() === oldPrefix.trim()) return;

      try {
        const plan = await index.planRefactorHierarchy(oldPrefix.trim(), newPrefix.trim());
        const confirm = await vscode.window.showInformationMessage(
          `Refactor ${plan.fileRenames.length} note(s) ("${oldPrefix.trim()}" → "${newPrefix.trim()}") and update ${plan.textEdits.length} link(s) across ${plan.affectedReferencingFiles} file(s)?`,
          { modal: true },
          "Refactor"
        );
        if (confirm !== "Refactor") return;
        const ok = await state.applyRefactorPlan(plan);
        if (ok) {
          vscode.window.showInformationMessage(
            `Refactored ${plan.fileRenames.length} notes and updated ${plan.textEdits.length} links.`
          );
        }
      } catch (err) {
        vscode.window.showErrorMessage(err instanceof Error ? err.message : String(err));
      }
    })
  );

  // 6. Copy Note Wikilink
  context.subscriptions.push(
    vscode.commands.registerCommand("sailzen.copyNoteLink", async () => {
      const fname = getActiveNoteFname(state);
      if (!fname) return;
      const note = state.vaultIndex?.getNote(fname);
      const link = note && note.title ? `[[${note.title}|${fname}]]` : `[[${fname}]]`;
      await vscode.env.clipboard.writeText(link);
      vscode.window.setStatusBarMessage(`Copied ${link}`, 2500);
    })
  );

  // 7. Go Up Hierarchy
  context.subscriptions.push(
    vscode.commands.registerCommand("sailzen.goUpHierarchy", async () => {
      const fname = getActiveNoteFname(state);
      if (!fname || !fname.includes(".")) return;
      const parent = fname.split(".").slice(0, -1).join(".");
      await state.openOrCreateNote(parent);
    })
  );

  // 8. Reload Vault
  context.subscriptions.push(
    vscode.commands.registerCommand("sailzen.reloadVault", async () => {
      await state.reloadVaultFull();
      const s = state.vaultIndex?.stats;
      if (s) {
        vscode.window.setStatusBarMessage(
          `SailZen: Indexed ${s.totalNotes} notes in ${s.durationMs}ms`,
          3000
        );
      }
    })
  );

  // 9. Switch Active Vault (Private / Work / Set Folder)
  context.subscriptions.push(
    vscode.commands.registerCommand("sailzen.switchVault", async () => {
      const priv = state.registry.getVaultSlot("private");
      const work = state.registry.getVaultSlot("work");
      const pick = await vscode.window.showQuickPick(
        [
          {
            label: "$(home) Private Vault (Cloud Sync Enabled)",
            description: priv?.path || "(not configured — click to pick folder)",
            action: "private" as const,
          },
          {
            label: "$(lock) Work Vault (Strict Offline Isolation)",
            description: work?.path || "(not configured — click to pick folder)",
            action: "work" as const,
          },
          {
            label: "$(gear) Open ~/.sailzen/machine.json",
            description: state.registry.configPath,
            action: "config" as const,
          },
        ],
        { placeHolder: "Select Active Vault or Edit Machine Config" }
      );
      if (!pick) return;

      if (pick.action === "config") {
        await vscode.commands.executeCommand("sailzen.openMachineConfig");
        return;
      }

      const slot = state.registry.getVaultSlot(pick.action);
      if (!slot?.path || !fs.existsSync(slot.path)) {
        const chosen = await vscode.window.showOpenDialog({
          canSelectFiles: false,
          canSelectFolders: true,
          canSelectMany: false,
          openLabel: `Select ${pick.action} Vault Root`,
        });
        if (!chosen || chosen.length === 0) return;
        await state.registry.setVaultPath(pick.action, chosen[0].fsPath);
      }
      await state.switchVault(pick.action);
    })
  );

  // 10. Toggle Tree Project Filter
  context.subscriptions.push(
    vscode.commands.registerCommand("sailzen.toggleTreeProjectFilter", () => {
      const active = state.toggleTreeProjectFilter();
      const ns = state.activeProject?.workbench.vault_namespace;
      vscode.window.setStatusBarMessage(
        active && ns ? `Vault Tree filtered to ${ns}.*` : "Vault Tree showing full hierarchy",
        2500
      );
    })
  );

  // 11. Refresh Rhythm & Projects
  context.subscriptions.push(
    vscode.commands.registerCommand("sailzen.refreshRhythm", async () => {
      await state.refreshServerData();
    })
  );

  // 12. Set Rhythm Block Status
  context.subscriptions.push(
    vscode.commands.registerCommand(
      "sailzen.blockSetStatus",
      async (item?: RhythmTreeItem) => {
        const blk = item?.payload as TimeBlockDTO | undefined;
        if (!blk || typeof blk !== "object" || !("id" in blk)) return;

        const chosen = await vscode.window.showQuickPick<
          vscode.QuickPickItem & { status: BlockStatus }
        >(
          [
            { label: "$(play-circle) DOING", status: "DOING" },
            { label: "$(pass-filled) DONE", status: "DONE" },
            { label: "$(circle-slash) SKIPPED", status: "SKIPPED" },
            { label: "$(circle-outline) PLANNED", status: "PLANNED" },
          ],
          { placeHolder: `Update status for "${blk.affair_title || blk.block_type}"` }
        );
        if (!chosen) return;
        try {
          await state.apiClient.setBlockStatus(blk.id, chosen.status);
          await state.refreshServerData();
        } catch (err) {
          vscode.window.showErrorMessage(err instanceof Error ? err.message : String(err));
        }
      }
    )
  );

  // 13. Pull Today's Rhythm into Current Journal (Fenced, non-destructive!)
  context.subscriptions.push(
    vscode.commands.registerCommand("sailzen.syncJournalRhythm", async () => {
      const editor = vscode.window.activeTextEditor;
      if (!editor || editor.document.languageId !== "markdown") {
        vscode.window.showWarningMessage("SailZen: Open a Markdown journal note first.");
        return;
      }
      if (state.privacyGuard.isWorkOfflineActive()) {
        vscode.window.showWarningMessage("SailZen: Work Vault offline mode blocks server sync.");
        return;
      }
      await state.refreshServerData();
      const boot = state.bootstrapData;
      if (!boot) {
        vscode.window.showWarningMessage("SailZen: Cannot reach sail_server.");
        return;
      }

      const fenced = formatRhythmSnapshotMarkdown(boot);
      const original = editor.document.getText();
      const updated = injectRhythmFencedSection(original, fenced);

      const fullRange = new vscode.Range(
        editor.document.positionAt(0),
        editor.document.positionAt(original.length)
      );
      await editor.edit((eb) => eb.replace(fullRange, updated));
      vscode.window.setStatusBarMessage("Synced today's Rhythm into journal fence", 2500);
    })
  );

  // 14. Push Selected Text to Rhythm Task (with PrivacyGuard!)
  context.subscriptions.push(
    vscode.commands.registerCommand("sailzen.pushSelectionToRhythm", async () => {
      const editor = vscode.window.activeTextEditor;
      if (!editor) return;
      const selected = editor.document.getText(editor.selection).trim();
      if (!selected) {
        vscode.window.showWarningMessage("SailZen: Select text first to push to Rhythm.");
        return;
      }

      const firstLine = selected.split(/\r?\n/)[0].replace(/^[-*#\s\[\]x]+/i, "").trim();
      const title = await vscode.window.showInputBox({
        prompt: "Push to Rhythm Task (title)",
        value: firstLine.slice(0, 120),
      });
      if (!title?.trim()) return;

      try {
        await state.apiClient.createQuickTask(title.trim(), {
          description: selected,
          sourceFsPath: editor.document.uri.fsPath,
        });
        vscode.window.showInformationMessage(`Pushed task to Rhythm: "${title.trim()}"`);
        void state.refreshServerData();
      } catch (err) {
        const msg =
          err instanceof PrivacyViolationError
            ? err.message
            : err instanceof Error
            ? err.message
            : String(err);
        vscode.window.showErrorMessage(msg);
      }
    })
  );

  // 15. Quick Add Rhythm Task
  context.subscriptions.push(
    vscode.commands.registerCommand("sailzen.addQuickTask", async () => {
      const title = await vscode.window.showInputBox({
        prompt: "Quick Add Rhythm Task",
        placeHolder: "e.g. Review chapter 3 outline",
      });
      if (!title?.trim()) return;
      try {
        await state.apiClient.createQuickTask(title.trim());
        void state.refreshServerData();
      } catch (err) {
        vscode.window.showErrorMessage(err instanceof Error ? err.message : String(err));
      }
    })
  );

  // 16. Complete Project Milestone
  context.subscriptions.push(
    vscode.commands.registerCommand(
      "sailzen.completeMilestone",
      async (item?: ProjectTreeItem) => {
        const ms = item?.payload as { id?: number; title?: string } | undefined;
        if (!ms?.id) return;
        try {
          await state.apiClient.completeMilestone(ms.id);
          await state.refreshServerData();
          vscode.window.setStatusBarMessage(`Completed milestone: ${ms.title}`, 2500);
        } catch (err) {
          vscode.window.showErrorMessage(err instanceof Error ? err.message : String(err));
        }
      }
    )
  );

  // 17. Bind Cloud Venture Project to Current Folder (Machine-local mapping!)
  context.subscriptions.push(
    vscode.commands.registerCommand("sailzen.bindProjectToCurrentFolder", async () => {
      const folder = vscode.workspace.workspaceFolders?.[0];
      if (!folder) {
        vscode.window.showWarningMessage("SailZen: Open a project folder in VS Code first.");
        return;
      }
      if (!state.bootstrapData) {
        await state.refreshServerData();
      }
      const projects = state.bootstrapData?.projects || [];
      if (projects.length === 0) {
        vscode.window.showWarningMessage("SailZen: No active Ventures loaded from server.");
        return;
      }

      const pick = await vscode.window.showQuickPick(
        projects.map((p) => ({
          label: p.progress.title,
          description: `${p.workbench.slug} (${p.workbench.archetype})`,
          project: p,
        })),
        { placeHolder: `Bind "${folder.uri.fsPath}" on THIS machine to Venture:` }
      );
      if (!pick) return;

      await state.registry.bindProjectPath(pick.project.workbench.slug, folder.uri.fsPath);
      state.resolveActiveProject();
      await state.refreshServerData();
      vscode.window.showInformationMessage(
        `Bound "${pick.project.workbench.slug}" → ${folder.uri.fsPath} (local machine config only).`
      );
    })
  );

  // 18. Copy AI Project Context Pack
  context.subscriptions.push(
    vscode.commands.registerCommand(
      "sailzen.copyContextPack",
      async (item?: ProjectTreeItem) => {
        let proj = item?.payload as WorkbenchProjectItemDTO | undefined;
        if (!proj || !("progress" in proj)) {
          proj = state.activeProject ?? undefined;
        }
        if (!proj) {
          const all = state.bootstrapData?.projects || [];
          const pick = await vscode.window.showQuickPick(
            all.map((p) => ({ label: p.progress.title, description: p.workbench.slug, proj: p })),
            { placeHolder: "Select project to generate AI Context Pack" }
          );
          proj = pick?.proj;
        }
        if (!proj) return;

        try {
          const pack = await state.apiClient.getContextPack(proj.progress.affair_id);
          await vscode.env.clipboard.writeText(pack.markdown);
          vscode.window.showInformationMessage(
            `Copied AI Context Pack for "${pack.title}" (${pack.markdown.length} chars) to clipboard.`
          );
        } catch (err) {
          vscode.window.showErrorMessage(err instanceof Error ? err.message : String(err));
        }
      }
    )
  );

  // 19. Open ~/.sailzen/machine.json
  context.subscriptions.push(
    vscode.commands.registerCommand("sailzen.openMachineConfig", async () => {
      await state.registry.ensureConfigFileExists();
      const doc = await vscode.workspace.openTextDocument(
        vscode.Uri.file(state.registry.configPath)
      );
      await vscode.window.showTextDocument(doc, { preview: false });
    })
  );

  // 20. Workbench Diagnostics
  context.subscriptions.push(
    vscode.commands.registerCommand("sailzen.showDiagnostics", async () => {
      const stats = state.vaultIndex?.stats;
      const lines = [
        `# SailZen Workbench Diagnostics`,
        `- Machine ID: ${state.registry.current.machineId}`,
        `- Config Path: ${state.registry.configPath}`,
        `- Active Vault Role: ${state.activeVaultRole}`,
        `- Active Vault Root: ${state.activeVaultRoot || "(none)"}`,
        `- Work Offline Active: ${state.privacyGuard.isWorkOfflineActive()}`,
        `- Indexed Notes: ${stats ? `${stats.totalNotes} (${stats.durationMs}ms, cacheHits=${stats.cacheHits})` : "0"}`,
        `- Server URL: ${state.registry.current.serverUrl}`,
        `- Server Online: ${state.isOnline} ${state.lastServerError ? `(${state.lastServerError})` : ""}`,
        `- Active Bound Project: ${state.activeProject ? `${state.activeProject.workbench.slug} (${state.activeProject.workbench.archetype})` : "(none)"}`,
      ];
      const doc = await vscode.workspace.openTextDocument({
        content: lines.join("\n"),
        language: "markdown",
      });
      await vscode.window.showTextDocument(doc, { preview: true });
    })
  );
}
