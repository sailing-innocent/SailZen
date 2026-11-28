import * as fs from "fs";
import * as path from "path";
import * as vscode from "vscode";
import { PrivacyViolationError } from "../../core/machine/privacyGuard";
import {
  runFullVaultContentSync,
  writeWorkClipsToVault,
} from "../../core/server/fencedSync";
import {
  checkForWorkbenchUpdate,
  downloadAndVerifyVsix,
} from "../../core/server/updater";
import { SailZenVfsUri } from "../../core/server/virtualFs";
import {
  BlockStatus,
  ContentTopicDTO,
  ProjectArchetype,
  TicketDTO,
  TimeBlockDTO,
  WorkbenchProjectItemDTO,
  WorkDTO,
} from "../../core/server/types";
import { WorkbenchState } from "../../core/workbenchState";
import {
  formatRhythmSnapshotMarkdown,
  injectRhythmFencedSection,
} from "../editor/journalBridge";
import { SailZenEditorProviders } from "../editor/wikilinkProvider";
import { ProjectTreeItem } from "../views/projectsView";
import { RhythmTreeItem } from "../views/rhythmView";
import { VaultTreeItem, VaultTreeLinkageController } from "../views/vaultTreeView";
import {
  buildFallbackContextPack,
  enrichContextPackWithLocalContext,
} from "../workflows/contextPacker";
import {
  parseChapterMarkdown,
  upsertChapterSyncFrontmatter,
} from "../workflows/novelWorkflow";
import {
  appendRecordEntry,
  buildSemanticRepoLink,
} from "../workflows/projectWorkflow";

interface LookupQuickPickItem extends vscode.QuickPickItem {
  fname: string;
  isCreateNew?: boolean;
}

function getActiveNoteFname(state: WorkbenchState): string | undefined {
  return state.resolveActiveVaultNoteFname();
}

function resolveTargetFname(state: WorkbenchState, item?: VaultTreeItem): string | undefined {
  if (item && item.node?.fname) {
    return item.node.fname;
  }
  return getActiveNoteFname(state);
}

export interface RegisterCommandsDeps {
  editorProviders?: SailZenEditorProviders;
  vaultTreeLinkage?: VaultTreeLinkageController;
}

export function registerWorkbenchCommands(
  context: vscode.ExtensionContext,
  state: WorkbenchState,
  deps?: RegisterCommandsDeps
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

  // 3. Create Note / Create Child Note
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
    }),
    vscode.commands.registerCommand("sailzen.createChildNote", async (item?: VaultTreeItem) => {
      const base = resolveTargetFname(state, item);
      const prefix = base ? `${base}.` : "";
      const fname = await vscode.window.showInputBox({
        prompt: "New child note dot-hierarchy name (without .md)",
        value: prefix,
        valueSelection: [prefix.length, prefix.length],
      });
      if (fname?.trim()) {
        await state.openOrCreateNote(fname.trim());
      }
    })
  );

  // 4. Quick Delete Note (Ctrl+Shift+D — moves to OS Trash + warns if referenced)
  context.subscriptions.push(
    vscode.commands.registerCommand("sailzen.deleteNote", async (item?: VaultTreeItem) => {
      const index = state.vaultIndex;
      const fname = resolveTargetFname(state, item);
      if (!index || !fname) {
        vscode.window.showWarningMessage("SailZen: Open or select a vault markdown note to delete.");
        return;
      }
      const note = index.getNote(fname);
      if (!note) {
        vscode.window.showWarningMessage(`SailZen: "${fname}" is a virtual node (no .md file).`);
        return;
      }

      const refs = index.getReferencingNotes(fname).filter((r) => r.fname !== note.fname);
      const refWarning =
        refs.length > 0
          ? ` ⚠️ ${refs.length} other note(s) link to it (${refs
              .slice(0, 3)
              .map((r) => r.fname)
              .join(", ")}${refs.length > 3 ? "..." : ""}).`
          : "";

      const confirm = await vscode.window.showWarningMessage(
        `Move note "${note.fname}.md" to Trash?${refWarning}`,
        { modal: true },
        "Move to Trash"
      );
      if (confirm !== "Move to Trash") return;

      const deleted = await state.deleteNoteToTrash(note.fname);
      if (deleted) {
        vscode.window.setStatusBarMessage(`Deleted ${note.fname}.md (moved to Trash)`, 3000);
      }
    })
  );

  // 5. Rename Note (Atomic cross-vault wikilink update — Editor & TreeView)
  context.subscriptions.push(
    vscode.commands.registerCommand("sailzen.renameNote", async (item?: VaultTreeItem) => {
      const index = state.vaultIndex;
      const oldFname = resolveTargetFname(state, item);
      if (!index || !oldFname) {
        vscode.window.showWarningMessage("SailZen: Open or select a vault markdown note to rename.");
        return;
      }
      if (!index.getNote(oldFname)) {
        vscode.window.showWarningMessage(
          `SailZen: "${oldFname}" is a virtual prefix. Use "Refactor Hierarchy" instead.`
        );
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

  // 6. Batch Rename Note (Pattern / Regex across vault + atomic cross-vault wikilink update)
  context.subscriptions.push(
    vscode.commands.registerCommand("sailzen.batchRenameNote", async (item?: VaultTreeItem) => {
      const index = state.vaultIndex;
      if (!index) {
        vscode.window.showWarningMessage("SailZen: No active vault configured.");
        return;
      }
      const initialScope = item?.node?.fname || getActiveNoteFname(state) || "";

      const modePick = await vscode.window.showQuickPick(
        [
          {
            label: "$(replace-all) Literal Substring Replace",
            description: "Replace matching text in note filenames (e.g. old-tag -> new-tag)",
            useRegex: false,
          },
          {
            label: "$(regex) Regular Expression Replace",
            description: "Use JS RegExp + capture groups ($1, $2) on note filenames",
            useRegex: true,
          },
        ],
        { placeHolder: "Batch Rename Mode (automatically updates all [[wikilinks]])" }
      );
      if (!modePick) return;

      const pattern = await vscode.window.showInputBox({
        prompt: modePick.useRegex
          ? "RegExp pattern to match in note filenames (e.g. ^dev-note\\.old\\.(.*)$)"
          : "Substring to find in note filenames",
        value: initialScope,
      });
      if (!pattern) return;

      const replacement = await vscode.window.showInputBox({
        prompt: modePick.useRegex
          ? `Replacement string for /${pattern}/g (supports $1, $2...)`
          : `Replace "${pattern}" with`,
        value: pattern,
      });
      if (replacement === undefined) return;

      try {
        const plan = await index.planBatchRename(pattern, replacement, {
          useRegex: modePick.useRegex,
        });
        if (plan.fileRenames.length === 0) {
          vscode.window.showInformationMessage(`No notes matched pattern "${pattern}".`);
          return;
        }

        const preview = plan.fileRenames
          .slice(0, 6)
          .map((r) => `• ${r.oldFname} → ${r.newFname}`)
          .join("\n");
        const more =
          plan.fileRenames.length > 6
            ? `\n... and ${plan.fileRenames.length - 6} more note(s)`
            : "";

        const confirm = await vscode.window.showInformationMessage(
          `Batch rename ${plan.fileRenames.length} note(s) and update ${plan.textEdits.length} link(s) across ${plan.affectedReferencingFiles} file(s)?\n\n${preview}${more}`,
          { modal: true },
          "Apply Batch Rename"
        );
        if (confirm !== "Apply Batch Rename") return;

        const ok = await state.applyRefactorPlan(plan);
        if (ok) {
          vscode.window.showInformationMessage(
            `Batch renamed ${plan.fileRenames.length} notes and updated ${plan.textEdits.length} links.`
          );
        }
      } catch (err) {
        vscode.window.showErrorMessage(err instanceof Error ? err.message : String(err));
      }
    })
  );

  // 7. Refactor Hierarchy (Atomic subtree rename + cross-vault link update)
  context.subscriptions.push(
    vscode.commands.registerCommand("sailzen.refactorHierarchy", async (item?: VaultTreeItem) => {
      const index = state.vaultIndex;
      if (!index) return;
      const current = resolveTargetFname(state, item) || "";
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

  // 8. Quick Copy Note Wikilink (Ctrl+Shift+C — Editor, Preview & TreeView)
  context.subscriptions.push(
    vscode.commands.registerCommand("sailzen.copyNoteLink", async (item?: VaultTreeItem) => {
      const fname = resolveTargetFname(state, item);
      if (!fname) {
        vscode.window.showWarningMessage("SailZen: Open or select a vault markdown note first.");
        return;
      }
      const note = state.vaultIndex?.getNote(fname);
      const link = note && note.title ? `[[${note.title}|${fname}]]` : `[[${fname}]]`;
      await vscode.env.clipboard.writeText(link);
      vscode.window.setStatusBarMessage(`Copied ${link}`, 2500);
    }),
    vscode.commands.registerCommand("sailzen.copyNoteRef", async (item?: VaultTreeItem) => {
      const fname = resolveTargetFname(state, item);
      if (!fname) {
        vscode.window.showWarningMessage("SailZen: Open or select a vault markdown note first.");
        return;
      }
      const ref = `![[${fname}]]`;
      await vscode.env.clipboard.writeText(ref);
      vscode.window.setStatusBarMessage(`Copied ${ref}`, 2500);
    }),
    vscode.commands.registerCommand("sailzen.followLinkAtCursor", async () => {
      const editor = vscode.window.activeTextEditor;
      if (!editor || editor.document.languageId !== "markdown") {
        vscode.window.showWarningMessage("SailZen: Focus a Markdown editor on a [[wikilink]] or repo:// link.");
        return;
      }
      const jumped = deps?.editorProviders
        ? await deps.editorProviders.followLinkAtCursor(editor)
        : false;
      if (!jumped) {
        vscode.window.setStatusBarMessage("SailZen: No [[wikilink]] or repo:// link at cursor", 2200);
      }
    }),
    vscode.commands.registerCommand("sailzen.showBacklinks", async (explicitFname?: string) => {
      const index = state.vaultIndex;
      const fname =
        typeof explicitFname === "string" && explicitFname.trim()
          ? explicitFname.trim()
          : getActiveNoteFname(state);
      if (!index || !fname) {
        vscode.window.showWarningMessage("SailZen: Open a vault markdown note to view backlinks.");
        return;
      }
      const refs = index
        .getReferencingNotes(fname)
        .filter((r) => r.fname.toLowerCase() !== fname.toLowerCase())
        .sort((a, b) => (b.updated || b.mtimeMs) - (a.updated || a.mtimeMs));

      if (refs.length === 0) {
        vscode.window.showInformationMessage(`SailZen: No notes link to "${fname}" yet.`);
        return;
      }

      const pick = await vscode.window.showQuickPick(
        refs.map((r) => ({
          label: `$(markdown) ${r.fname}`,
          description: r.title !== r.fname ? r.title : "",
          detail: r.tags.length > 0 ? r.tags.map((t) => `#${t}`).join(" ") : undefined,
          note: r,
        })),
        {
          placeHolder: `${refs.length} backlink(s) referencing "${fname}"`,
          matchOnDescription: true,
        }
      );
      if (!pick) return;
      await state.openOrCreateNote(pick.note.fname);
    })
  );

  // 9. Dot-Hierarchy Navigation (Up / Down / Next Sibling / Prev Sibling) & Sidebar Linkage
  context.subscriptions.push(
    vscode.commands.registerCommand("sailzen.goUpHierarchy", async () => {
      const fname = getActiveNoteFname(state);
      if (!fname || !fname.includes(".")) return;
      const parent = fname.split(".").slice(0, -1).join(".");
      await state.openOrCreateNote(parent);
    }),
    vscode.commands.registerCommand("sailzen.goDownHierarchy", async () => {
      const index = state.vaultIndex;
      const fname = getActiveNoteFname(state);
      if (!index || !fname) return;
      const children = index.getChildren(fname);
      if (children.length === 0) {
        vscode.window.setStatusBarMessage(`SailZen: "${fname}" has no child notes`, 2200);
        return;
      }
      if (children.length === 1 && children[0].note) {
        await state.openOrCreateNote(children[0].note.fname);
        return;
      }
      const pick = await vscode.window.showQuickPick(
        children.map((c) => ({
          label: `${c.note ? "$(markdown)" : "$(folder)"} ${c.segment}`,
          description: c.note?.title && c.note.title !== c.segment ? c.note.title : c.fname,
          detail: c.note ? undefined : "Virtual hierarchy node — select to create note",
          fname: c.fname,
        })),
        { placeHolder: `Children of "${fname}" (${children.length})` }
      );
      if (pick) {
        await state.openOrCreateNote(pick.fname);
      }
    }),
    vscode.commands.registerCommand("sailzen.goNextSibling", async () => {
      const index = state.vaultIndex;
      const fname = getActiveNoteFname(state);
      if (!index || !fname) return;
      const next = index.getAdjacentSiblingNote(fname, 1);
      if (next) {
        await state.openOrCreateNote(next.fname);
      } else {
        vscode.window.setStatusBarMessage(`SailZen: No other sibling notes for "${fname}"`, 2000);
      }
    }),
    vscode.commands.registerCommand("sailzen.goPrevSibling", async () => {
      const index = state.vaultIndex;
      const fname = getActiveNoteFname(state);
      if (!index || !fname) return;
      const prev = index.getAdjacentSiblingNote(fname, -1);
      if (prev) {
        await state.openOrCreateNote(prev.fname);
      } else {
        vscode.window.setStatusBarMessage(`SailZen: No other sibling notes for "${fname}"`, 2000);
      }
    }),
    vscode.commands.registerCommand("sailzen.revealActiveNoteInTree", async () => {
      const revealed = deps?.vaultTreeLinkage
        ? await deps.vaultTreeLinkage.revealActiveNote({ focus: true, force: true })
        : false;
      if (!revealed) {
        vscode.window.showInformationMessage(
          "SailZen: Focus a markdown note inside the active vault to reveal it in Vault Tree."
        );
      }
    }),
    vscode.commands.registerCommand("sailzen.openCloudSidebar", async () => {
      try {
        await vscode.commands.executeCommand("workbench.view.extension.sailzen-cloud");
      } catch {
        await vscode.commands.executeCommand("sailzen.rhythmView.focus");
      }
    })
  );

  // 10. Reload Vault
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

  // 11. Switch Active Vault (Private / Work / Set Folder)
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

  // 12. Toggle Tree Project Filter
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

  // 13. Open Project Note (Dual-mode shortcut inside code repos!)
  context.subscriptions.push(
    vscode.commands.registerCommand("sailzen.openProjectNote", async () => {
      const ns = state.activeProject?.workbench.vault_namespace;
      const prefix = ns ? `${ns}.` : "";
      await vscode.commands.executeCommand("sailzen.lookupNote", prefix);
    })
  );

  // 14. Refresh Rhythm & Projects
  context.subscriptions.push(
    vscode.commands.registerCommand("sailzen.refreshRhythm", async () => {
      await state.refreshServerData();
    })
  );

  // 15. Set Rhythm Block Status
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
    ),
    vscode.commands.registerCommand(
      "sailzen.interactTicket",
      async (item?: RhythmTreeItem) => {
        const ticket = item?.payload as TicketDTO | undefined;
        if (!ticket || typeof ticket !== "object" || !("id" in ticket)) return;
        if (state.privacyGuard.isWorkOfflineActive()) {
          vscode.window.showWarningMessage("SailZen: Work Vault offline mode blocks SailTick actions.");
          return;
        }

        const quickReplies = Array.isArray(ticket.meta?.quick_replies)
          ? (ticket.meta?.quick_replies as unknown[])
              .filter((x): x is string => typeof x === "string" && x.trim().length > 0)
          : [];

        type TicketActionPick = vscode.QuickPickItem & {
          action: "quick_reply" | "custom_reply" | "snooze_1h" | "snooze_24h";
          replyText?: string;
        };

        const picks: TicketActionPick[] = [
          ...quickReplies.map((qr) => ({
            label: `$(reply) ${qr}`,
            description: "Quick reply",
            action: "quick_reply" as const,
            replyText: qr,
          })),
          {
            label: "$(edit) 自由输入回复...",
            description: ticket.body ? ticket.body.slice(0, 80) : "",
            action: "custom_reply" as const,
          },
          {
            label: "$(clock) 延后 1 小时",
            action: "snooze_1h" as const,
          },
          {
            label: "$(bell-slash) 延后 24 小时",
            action: "snooze_24h" as const,
          },
        ];

        const chosen = await vscode.window.showQuickPick<TicketActionPick>(picks, {
          placeHolder: `${ticket.title}${ticket.body ? " — " + ticket.body.slice(0, 60) : ""}`,
        });
        if (!chosen) return;

        try {
          if (chosen.action === "quick_reply" && chosen.replyText) {
            await state.apiClient.replyTicket(ticket.id, chosen.replyText);
            vscode.window.setStatusBarMessage(`Replied to SailTick #${ticket.id}`, 2500);
          } else if (chosen.action === "custom_reply") {
            const input = await vscode.window.showInputBox({
              prompt: `Reply to "${ticket.title}"`,
              placeHolder: "输入你的回复...",
            });
            if (!input?.trim()) return;
            await state.apiClient.replyTicket(ticket.id, input.trim());
            vscode.window.setStatusBarMessage(`Replied to SailTick #${ticket.id}`, 2500);
          } else if (chosen.action === "snooze_1h") {
            await state.apiClient.snoozeTicket(ticket.id, 1);
            vscode.window.setStatusBarMessage(`Snoozed SailTick #${ticket.id} for 1h`, 2500);
          } else if (chosen.action === "snooze_24h") {
            await state.apiClient.snoozeTicket(ticket.id, 24);
            vscode.window.setStatusBarMessage(`Snoozed SailTick #${ticket.id} for 24h`, 2500);
          }
          await state.refreshServerData();
        } catch (err) {
          vscode.window.showErrorMessage(err instanceof Error ? err.message : String(err));
        }
      }
    )
  );

  // 16. Pull Today's Rhythm into Current Journal (Fenced, non-destructive; supports native vscode.markdown.editor!)
  context.subscriptions.push(
    vscode.commands.registerCommand("sailzen.syncJournalRhythm", async () => {
      const doc = await state.resolveActiveMarkdownDocument();
      if (!doc) {
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
      const original = doc.getText();
      const updated = injectRhythmFencedSection(original, fenced);

      const wsEdit = new vscode.WorkspaceEdit();
      wsEdit.replace(
        doc.uri,
        new vscode.Range(doc.positionAt(0), doc.positionAt(original.length)),
        updated
      );
      await vscode.workspace.applyEdit(wsEdit);
      await doc.save();
      vscode.window.setStatusBarMessage("Synced today's Rhythm into journal fence", 2500);
    })
  );

  // 17. Push Selected Text to Rhythm Task (with PrivacyGuard!)
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

  // 18. Quick Add Rhythm Task
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

  // 19. Complete Project Milestone
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

  // 20. Bind Cloud Venture Project to Current Folder (Machine-local mapping!)
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

  // 21. Configure Venture Semantic Metadata (Cloud-shared across all machines)
  context.subscriptions.push(
    vscode.commands.registerCommand(
      "sailzen.configureProjectMeta",
      async (item?: ProjectTreeItem) => {
        let proj = item?.payload as WorkbenchProjectItemDTO | undefined;
        if (!proj || !("progress" in proj)) {
          const all = state.bootstrapData?.projects || [];
          const pick = await vscode.window.showQuickPick(
            all.map((p) => ({
              label: p.progress.title,
              description: `${p.workbench.slug} (${p.workbench.archetype})`,
              proj: p,
            })),
            { placeHolder: "Select Venture to configure semantic metadata" }
          );
          proj = pick?.proj;
        }
        if (!proj) return;

        const slug = await vscode.window.showInputBox({
          prompt: "Semantic project slug (lowercase, cross-machine identifier)",
          value: proj.workbench.slug,
        });
        if (!slug?.trim()) return;

        const archPick = await vscode.window.showQuickPick<
          vscode.QuickPickItem & { value: ProjectArchetype }
        >(
          [
            { label: "novel — 长篇小说创作", value: "novel" },
            { label: "game — 独立游戏开发", value: "game" },
            { label: "research — 科研推进", value: "research" },
            { label: "engineering — 系统工程", value: "engineering" },
            { label: "general — 通用项目", value: "general" },
          ],
          { placeHolder: `Current archetype: ${proj.workbench.archetype}` }
        );
        if (!archPick) return;

        const vaultNamespace = await vscode.window.showInputBox({
          prompt: "Linked Vault namespace prefix (e.g. project.hat-factory, leave blank if none)",
          value: proj.workbench.vault_namespace,
        });
        if (vaultNamespace === undefined) return;

        const hintsRaw = await vscode.window.showInputBox({
          prompt: "Semantic repo hints (comma-separated repo names, NO local drive paths)",
          value: proj.workbench.repo_hints.join(", "),
        });
        if (hintsRaw === undefined) return;
        const repo_hints = hintsRaw
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean);

        try {
          await state.apiClient.updateProjectMeta(proj.progress.affair_id, {
            slug: slug.trim(),
            archetype: archPick.value,
            vault_namespace: vaultNamespace.trim(),
            repo_hints,
          });
          await state.refreshServerData();
          vscode.window.showInformationMessage(`Updated semantic metadata for "${slug.trim()}".`);
        } catch (err) {
          vscode.window.showErrorMessage(err instanceof Error ? err.message : String(err));
        }
      }
    )
  );

  // 22. Content 2.0: Open Virtual Document (sailzen://)
  context.subscriptions.push(
    vscode.commands.registerCommand("sailzen.openVirtualUri", async (uri?: vscode.Uri) => {
      if (!uri) return;
      try {
        const doc = await vscode.workspace.openTextDocument(uri);
        await vscode.window.showTextDocument(doc, { preview: true });
      } catch (err) {
        vscode.window.showErrorMessage(
          `Failed to open cloud document: ${err instanceof Error ? err.message : String(err)}`
        );
      }
    })
  );

  // 23. Content 2.0: Full Fenced Bidirectional Vault Sync (read.* / topic.* / study.*)
  context.subscriptions.push(
    vscode.commands.registerCommand("sailzen.syncVaultContent", async () => {
      const index = state.vaultIndex;
      const vaultRoot = state.activeVaultRoot;
      if (!index || !vaultRoot) {
        vscode.window.showWarningMessage("SailZen: No active vault configured.");
        return;
      }
      try {
        state.privacyGuard.assertCloudUploadAllowed("syncVaultContent", vaultRoot);
        const report = await vscode.window.withProgress(
          {
            location: vscode.ProgressLocation.Notification,
            title: "SailZen: Syncing Vault ↔ Content 2.0...",
            cancellable: false,
          },
          () =>
            runFullVaultContentSync(
              index,
              state.apiClient,
              vaultRoot,
              state.registry.current.machineId
            )
        );
        await state.reloadVaultFull();
        vscode.window.showInformationMessage(
          `Content 2.0 Sync Done — Upstream: ${report.upstreamCreated} created / ${report.upstreamUpdated} updated / ${report.upstreamSkipped} unchanged; Downstream: ${report.downstreamWorksExported} work(s) exported.`
        );
      } catch (err) {
        vscode.window.showErrorMessage(err instanceof Error ? err.message : String(err));
      }
    })
  );

  // 24. Content 2.0: Export Single Work Reading Card & Clips to Private Vault (Fenced)
  context.subscriptions.push(
    vscode.commands.registerCommand(
      "sailzen.syncWorkToVault",
      async (item?: ProjectTreeItem) => {
        const work = item?.payload as WorkDTO | undefined;
        const index = state.vaultIndex;
        const vaultRoot = state.activeVaultRoot;
        if (!work?.id || !index || !vaultRoot) return;

        try {
          state.privacyGuard.assertCloudUploadAllowed("syncWorkToVault", vaultRoot);
          const exp = await state.apiClient.exportWorkClips(work.id);
          const res = await writeWorkClipsToVault(index.notesDir, exp);
          await index.upsertFile(res.cardPath);
          await index.upsertFile(res.clipsPath);
          await vscode.commands.executeCommand("vscode.open", vscode.Uri.file(res.cardPath), {
            preview: false,
          });
          vscode.window.showInformationMessage(
            `Exported "${work.title}" (${res.cardAction} reading card + clips, handwritten notes preserved).`
          );
        } catch (err) {
          vscode.window.showErrorMessage(err instanceof Error ? err.message : String(err));
        }
      }
    )
  );

  // 25. Content 2.0: Push Topic Milestone Task to Rhythm
  context.subscriptions.push(
    vscode.commands.registerCommand(
      "sailzen.pushTopicTask",
      async (item?: ProjectTreeItem) => {
        const topic = item?.payload as ContentTopicDTO | undefined;
        if (!topic?.id) return;
        const title = await vscode.window.showInputBox({
          prompt: `Push task from Topic "${topic.title}" to Rhythm`,
          placeHolder: "e.g. 精读论文方法章节并整理实验笔记",
        });
        if (!title?.trim()) return;
        try {
          await state.apiClient.pushTopicRhythmTask(topic.id, { title: title.trim() });
          await state.refreshServerData();
          vscode.window.showInformationMessage(`Pushed topic task "${title.trim()}" to Rhythm.`);
        } catch (err) {
          vscode.window.showErrorMessage(err instanceof Error ? err.message : String(err));
        }
      }
    )
  );

  // 26. Copy AI Project Context Pack (with graceful fallback + local Vault/file enrichment)
  const buildEnrichedContextPack = async (
    proj: WorkbenchProjectItemDTO
  ): Promise<{ title: string; slug: string; markdown: string }> => {
    let baseMarkdown: string;
    try {
      const pack = await state.apiClient.getContextPack(proj.progress.affair_id);
      baseMarkdown = pack.markdown;
    } catch {
      baseMarkdown = buildFallbackContextPack(proj);
    }

    let activeFileSemanticLink: string | undefined;
    const editor = vscode.window.activeTextEditor;
    if (editor && editor.document.uri.scheme === "file") {
      const localRoot = state.registry.resolveProjectPath(proj.workbench.slug);
      if (localRoot) {
        try {
          const line = editor.selection.active.line + 1;
          activeFileSemanticLink = buildSemanticRepoLink({
            projectSlug: proj.workbench.slug,
            repoRoot: localRoot,
            fileFsPath: editor.document.uri.fsPath,
            line,
          }).markdown;
        } catch {
          // Active file is outside this project repo
        }
      }
    }

    const markdown = enrichContextPackWithLocalContext(baseMarkdown, {
      machineId: state.registry.current.machineId,
      activeFileSemanticLink,
      vaultNamespace: proj.workbench.vault_namespace || undefined,
      vaultIndex: state.vaultIndex,
    });
    return { title: proj.progress.title, slug: proj.workbench.slug, markdown };
  };

  const pickProjectForContext = async (
    item?: ProjectTreeItem
  ): Promise<WorkbenchProjectItemDTO | undefined> => {
    const fromItem = item?.payload as WorkbenchProjectItemDTO | undefined;
    if (fromItem && "progress" in fromItem) return fromItem;
    if (state.activeProject) return state.activeProject;
    const all = state.bootstrapData?.projects || [];
    const pick = await vscode.window.showQuickPick(
      all.map((p) => ({ label: p.progress.title, description: p.workbench.slug, proj: p })),
      { placeHolder: "Select project to generate AI Context Pack" }
    );
    return pick?.proj;
  };

  context.subscriptions.push(
    vscode.commands.registerCommand(
      "sailzen.copyContextPack",
      async (item?: ProjectTreeItem) => {
        if (state.privacyGuard.isWorkOfflineActive()) {
          vscode.window.showWarningMessage("SailZen: Work Vault offline mode blocks AI Context Pack.");
          return;
        }
        const proj = await pickProjectForContext(item);
        if (!proj) return;
        try {
          const pack = await buildEnrichedContextPack(proj);
          await vscode.env.clipboard.writeText(pack.markdown);
          vscode.window.showInformationMessage(
            `Copied AI Context Pack for "${pack.title}" (${pack.markdown.length} chars) to clipboard.`
          );
        } catch (err) {
          vscode.window.showErrorMessage(err instanceof Error ? err.message : String(err));
        }
      }
    ),
    vscode.commands.registerCommand(
      "sailzen.writeContextPackFile",
      async (item?: ProjectTreeItem) => {
        if (state.privacyGuard.isWorkOfflineActive()) {
          vscode.window.showWarningMessage("SailZen: Work Vault offline mode blocks AI Context Pack.");
          return;
        }
        const folder = vscode.workspace.workspaceFolders?.[0];
        if (!folder) {
          vscode.window.showWarningMessage("SailZen: Open a workspace folder first.");
          return;
        }
        const proj = await pickProjectForContext(item);
        if (!proj) return;
        try {
          const pack = await buildEnrichedContextPack(proj);
          const outDir = path.join(folder.uri.fsPath, ".sailzen");
          await fs.promises.mkdir(outDir, { recursive: true });
          const outPath = path.join(outDir, "context-pack.md");
          await fs.promises.writeFile(outPath, pack.markdown, "utf8");
          const doc = await vscode.workspace.openTextDocument(vscode.Uri.file(outPath));
          await vscode.window.showTextDocument(doc, { preview: true });
          vscode.window.showInformationMessage(`Wrote AI Context Pack to ${outPath}`);
        } catch (err) {
          vscode.window.showErrorMessage(err instanceof Error ? err.message : String(err));
        }
      }
    )
  );

  // 27. Library UX: Pin / Unpin Work & QuickPick Search All Works
  context.subscriptions.push(
    vscode.commands.registerCommand(
      "sailzen.togglePinWork",
      async (item?: ProjectTreeItem) => {
        const work = item?.payload as WorkDTO | undefined;
        if (!work?.id) return;
        const pinned = await state.togglePinWork(work.id);
        vscode.window.setStatusBarMessage(
          pinned ? `Pinned "${work.title}"` : `Unpinned "${work.title}"`,
          2500
        );
      }
    ),
    vscode.commands.registerCommand("sailzen.searchLibrary", async () => {
      if (state.privacyGuard.isWorkOfflineActive()) {
        vscode.window.showWarningMessage("SailZen: Work Vault offline mode blocks cloud library.");
        return;
      }
      if (state.works.length === 0) {
        await state.refreshServerData();
      }
      if (state.works.length === 0) {
        vscode.window.showInformationMessage("SailZen: No works loaded from server.");
        return;
      }

      const workPick = await vscode.window.showQuickPick(
        state.works.map((w) => {
          const pin = state.registry.isWorkPinned(w.id) ? "📌 " : "";
          const orig = w.is_original ? "✍ " : "";
          return {
            label: `${pin}${orig}${w.title}`,
            description: `${w.pillar} · ${w.reading_status}${w.progress_pct != null ? ` · ${Math.round(w.progress_pct)}%` : ""}`,
            detail: w.author || w.work_type,
            work: w,
          };
        }),
        { placeHolder: `Search ${state.works.length} cloud works by title, author, or pillar...`, matchOnDescription: true, matchOnDetail: true }
      );
      if (!workPick) return;
      const work = workPick.work;
      const isPinned = state.registry.isWorkPinned(work.id);

      const action = await vscode.window.showQuickPick(
        [
          { label: "$(list-tree) Open Chapter (Virtual)", id: "chapter" },
          { label: "$(quote) Open Clips & Highlights (Virtual)", id: "clips" },
          { label: "$(desktop-download) Export Reading Card & Clips to Vault", id: "export" },
          { label: isPinned ? "$(pinned) Unpin from Library" : "$(pin) Pin to Top of Library", id: "pin" },
        ],
        { placeHolder: `Action for "${work.title}"` }
      );
      if (!action) return;

      if (action.id === "pin") {
        await state.togglePinWork(work.id);
      } else if (action.id === "clips") {
        await vscode.commands.executeCommand(
          "sailzen.openVirtualUri",
          SailZenVfsUri.clips(work.id, work.vault_slug || work.slug)
        );
      } else if (action.id === "export") {
        await vscode.commands.executeCommand(
          "sailzen.syncWorkToVault",
          new ProjectTreeItem(work.title, "work", vscode.TreeItemCollapsibleState.None, work)
        );
      } else if (action.id === "chapter") {
        try {
          const editions = await state.apiClient.getEditionsByWork(work.id);
          if (editions.length === 0) {
            vscode.window.showInformationMessage("No editions found for this work.");
            return;
          }
          const canonical = editions.find((e) => e.canonical) || editions[0];
          const toc = await state.apiClient.getEditionToc(canonical.id);
          const allChapters = [
            ...toc.volumes.flatMap((v) =>
              v.chapters.map((c) => ({ ch: c, vol: [v.label, v.title].filter(Boolean).join(" ") }))
            ),
            ...toc.ungrouped_chapters.map((c) => ({ ch: c, vol: "" })),
          ];
          const chPick = await vscode.window.showQuickPick(
            allChapters.map(({ ch, vol }) => ({
              label: [ch.label, ch.title].filter(Boolean).join(" ") || `Chapter ${ch.sort_index + 1}`,
              description: vol || (ch.char_count ? `${ch.char_count} chars` : ""),
              ch,
            })),
            { placeHolder: `Select chapter in "${work.title}" (${allChapters.length} chapters)` }
          );
          if (!chPick) return;
          await vscode.commands.executeCommand(
            "sailzen.openVirtualUri",
            SailZenVfsUri.chapter(work.id, chPick.ch.id, chPick.label)
          );
        } catch (err) {
          vscode.window.showErrorMessage(err instanceof Error ? err.message : String(err));
        }
      }
    })
  );

  // 28. Novel Workflow: Sync Local Chapter Markdown -> Cloud DocumentNode (supports native vscode.markdown.editor!)
  context.subscriptions.push(
    vscode.commands.registerCommand("sailzen.syncChapterToCloud", async () => {
      const doc = await state.resolveActiveMarkdownDocument();
      if (!doc || doc.uri.scheme !== "file") {
        vscode.window.showWarningMessage("SailZen: Open a Markdown chapter file first.");
        return;
      }
      const fsPath = doc.uri.fsPath;
      try {
        state.privacyGuard.assertCloudUploadAllowed("syncChapterToCloud", fsPath);
      } catch (err) {
        vscode.window.showErrorMessage(err instanceof Error ? err.message : String(err));
        return;
      }

      const raw = doc.getText();
      const parsed = parseChapterMarkdown(fsPath, raw);

      let workId = parsed.workId ?? state.activeProject?.workbench.original_work_id ?? undefined;
      let editionId = parsed.editionId;

      if (!workId) {
        if (state.works.length === 0) await state.refreshServerData();
        const originals = state.works.filter((w) => w.is_original);
        const candidates = originals.length > 0 ? originals : state.works;
        if (candidates.length === 0) {
          vscode.window.showWarningMessage("SailZen: No works available on server.");
          return;
        }
        const pick = await vscode.window.showQuickPick(
          candidates.map((w) => ({
            label: `${w.is_original ? "✍ " : ""}${w.title}`,
            description: `${w.work_type} · ${w.slug}`,
            work: w,
          })),
          { placeHolder: "Select target Work to sync this chapter to" }
        );
        if (!pick) return;
        workId = pick.work.id;
      }

      if (!editionId) {
        try {
          const editions = await state.apiClient.getEditionsByWork(workId);
          if (editions.length === 0) {
            vscode.window.showWarningMessage(`Work #${workId} has no editions on server.`);
            return;
          }
          editionId = (editions.find((e) => e.canonical) || editions[0]).id;
        } catch (err) {
          vscode.window.showErrorMessage(err instanceof Error ? err.message : String(err));
          return;
        }
      }

      try {
        const res = await state.apiClient.syncEditionChapter(
          editionId,
          {
            node_id: parsed.nodeId,
            source_slug: parsed.sourceSlug,
            label: parsed.label || undefined,
            title: parsed.title,
            content: parsed.body,
          },
          fsPath
        );

        // Record sync IDs cleanly in frontmatter on first sync or node_id change
        if (
          parsed.workId !== workId ||
          parsed.editionId !== editionId ||
          parsed.nodeId !== res.node.id
        ) {
          const updatedText = upsertChapterSyncFrontmatter(raw, {
            workId,
            editionId,
            nodeId: res.node.id,
            sourceSlug: parsed.sourceSlug,
          });
          const wsEdit = new vscode.WorkspaceEdit();
          wsEdit.replace(
            doc.uri,
            new vscode.Range(doc.positionAt(0), doc.positionAt(raw.length)),
            updatedText
          );
          await vscode.workspace.applyEdit(wsEdit);
          await doc.save();
        }

        vscode.window.showInformationMessage(
          `Synced chapter "${parsed.title}" (${res.action}, node #${res.node.id}, ${parsed.wordCount} words | edition total: ${res.edition_word_count} words).`
        );
      } catch (err) {
        vscode.window.showErrorMessage(err instanceof Error ? err.message : String(err));
      }
    })
  );

  // 29. Novel/AI Workflow: Diff Local Note vs Cloud NoteItem (AI Draft Review)
  context.subscriptions.push(
    vscode.commands.registerCommand("sailzen.reviewNoteItemDiff", async () => {
      const localUri = state.resolveActiveFileUri();
      if (!localUri || localUri.scheme !== "file") {
        vscode.window.showWarningMessage("SailZen: Open a local Markdown note to compare against a cloud NoteItem.");
        return;
      }
      if (state.privacyGuard.isWorkOfflineActive()) {
        vscode.window.showWarningMessage("SailZen: Work Vault offline mode blocks cloud NoteItem diff.");
        return;
      }
      if (state.noteItems.length === 0) {
        await state.refreshServerData();
      }
      if (state.noteItems.length === 0) {
        vscode.window.showInformationMessage("SailZen: No cloud NoteItems found on server.");
        return;
      }

      const pick = await vscode.window.showQuickPick(
        state.noteItems.map((ni) => ({
          label: ni.title || ni.slug || `NoteItem #${ni.id}`,
          description: ni.category,
          detail: ni.setting_file,
          ni,
        })),
        { placeHolder: "Select cloud Story Bible / AI NoteItem to diff with current file" }
      );
      if (!pick) return;

      const title = pick.ni.title || pick.ni.slug || `NoteItem-${pick.ni.id}`;
      const cloudUri = SailZenVfsUri.noteItem(pick.ni.id, title);
      await vscode.commands.executeCommand(
        "vscode.diff",
        localUri,
        cloudUri,
        `Local ↔ Cloud NoteItem (${title})`
      );
    })
  );

  // 30. Game / Research / Engineering Workflow: Copy Cross-Machine Semantic repo:// Link
  context.subscriptions.push(
    vscode.commands.registerCommand("sailzen.copySemanticCodeLink", async () => {
      const editor = vscode.window.activeTextEditor;
      if (!editor || editor.document.uri.scheme !== "file") {
        vscode.window.showWarningMessage("SailZen: Open a local source file first.");
        return;
      }
      const fsPath = editor.document.uri.fsPath;
      let slug = state.registry.findProjectSlugForFolder(fsPath);
      if (!slug && state.activeProject) {
        slug = state.activeProject.workbench.slug;
      }
      if (!slug) {
        const ans = await vscode.window.showWarningMessage(
          "This folder is not bound to a SailZen project on this machine yet. Bind it now?",
          "Bind Project"
        );
        if (ans === "Bind Project") {
          await vscode.commands.executeCommand("sailzen.bindProjectToCurrentFolder");
        }
        return;
      }
      const repoRoot = state.registry.resolveProjectPath(slug);
      if (!repoRoot) {
        vscode.window.showWarningMessage(`SailZen: Local path for "${slug}" not found in machine.json.`);
        return;
      }
      try {
        const line = editor.selection.active.line + 1;
        const link = buildSemanticRepoLink({
          projectSlug: slug,
          repoRoot,
          fileFsPath: fsPath,
          line,
        });
        await vscode.env.clipboard.writeText(link.markdown);
        vscode.window.setStatusBarMessage(`Copied semantic link ${link.markdown}`, 3000);
      } catch (err) {
        vscode.window.showErrorMessage(err instanceof Error ? err.message : String(err));
      }
    })
  );

  // 31. Game / Research / Engineering Workflow: Log Current Code Context to Today's Journal
  context.subscriptions.push(
    vscode.commands.registerCommand("sailzen.logToTodayJournal", async () => {
      const editor = vscode.window.activeTextEditor;
      if (!editor || editor.document.uri.scheme !== "file") {
        vscode.window.showWarningMessage("SailZen: Open a file first.");
        return;
      }
      const fsPath = editor.document.uri.fsPath;
      const line = editor.selection.active.line + 1;
      const selected = editor.document.getText(editor.selection).trim();

      let refPart = `\`${path.basename(fsPath)}:L${line}\``;
      const slug = state.registry.findProjectSlugForFolder(fsPath);
      if (slug) {
        const repoRoot = state.registry.resolveProjectPath(slug);
        if (repoRoot) {
          try {
            refPart = buildSemanticRepoLink({
              projectSlug: slug,
              repoRoot,
              fileFsPath: fsPath,
              line,
            }).markdown;
          } catch {
            // fallback to basename
          }
        }
      }

      const noteText = await vscode.window.showInputBox({
        prompt: "Engineering / Experiment / Dev log entry (appended to Today's Journal ## Record)",
        value: selected ? selected.split(/\r?\n/)[0].slice(0, 100) : "",
        placeHolder: "What did you discover, fix, or decide?",
      });
      if (!noteText?.trim()) return;

      const journalDoc = await state.openDailyJournal(new Date());
      if (!journalDoc) return;
      const original = journalDoc.getText();
      const updated = appendRecordEntry(original, `${refPart} — ${noteText.trim()}`);
      const wsEdit = new vscode.WorkspaceEdit();
      wsEdit.replace(
        journalDoc.uri,
        new vscode.Range(journalDoc.positionAt(0), journalDoc.positionAt(original.length)),
        updated
      );
      await vscode.workspace.applyEdit(wsEdit);
      await journalDoc.save();
      vscode.window.setStatusBarMessage("Appended dev log entry to Today's Journal", 2500);
    })
  );

  // 32. Research Workflow: Insert Cloud Paper / Book Reference into Active Markdown
  context.subscriptions.push(
    vscode.commands.registerCommand("sailzen.insertPaperReference", async () => {
      const editor = vscode.window.activeTextEditor;
      if (!editor) {
        vscode.window.showWarningMessage("SailZen: Open a Markdown note first.");
        return;
      }
      if (state.privacyGuard.isWorkOfflineActive()) {
        vscode.window.showWarningMessage("SailZen: Work Vault offline mode blocks cloud library.");
        return;
      }
      if (state.works.length === 0) await state.refreshServerData();
      if (state.works.length === 0) {
        vscode.window.showInformationMessage("SailZen: No cloud works available.");
        return;
      }

      const activeTopicId = state.activeProject?.workbench.topic_id;
      const sorted = [...state.works].sort((a, b) => {
        const aHit = activeTopicId && a.topic_ids?.includes(activeTopicId) ? 0 : 1;
        const bHit = activeTopicId && b.topic_ids?.includes(activeTopicId) ? 0 : 1;
        if (aHit !== bHit) return aHit - bHit;
        return a.title.localeCompare(b.title);
      });

      const pick = await vscode.window.showQuickPick(
        sorted.map((w) => ({
          label: `${activeTopicId && w.topic_ids?.includes(activeTopicId) ? "★ " : ""}${w.title}`,
          description: `${w.pillar} · ${w.work_type}`,
          detail: w.author || w.source_url || "",
          work: w,
        })),
        { placeHolder: "Select paper / book to cite in current note", matchOnDescription: true, matchOnDetail: true }
      );
      if (!pick) return;
      const w = pick.work;
      const refMd = w.vault_slug
        ? `[[${w.title}|read.${w.vault_slug}]]`
        : w.source_url
        ? `[${w.title}](${w.source_url})`
        : `**${w.title}**${w.author ? ` (${w.author})` : ""}`;

      await editor.edit((eb) => eb.insert(editor.selection.active, refMd));
    })
  );

  // 33. OTA Self-Update: Check & Install Latest VSIX directly from cloud sail_server
  context.subscriptions.push(
    vscode.commands.registerCommand(
      "sailzen.checkForUpdate",
      async (opts?: { silent?: boolean }) => {
        const silent = Boolean(opts?.silent);
        if (state.privacyGuard.isWorkOfflineActive()) {
          if (!silent) {
            vscode.window.showWarningMessage(
              "SailZen: Work Vault offline mode disables cloud OTA update checks."
            );
          }
          return;
        }

        state.reloadConfig();
        const currentVersion = String(context.extension.packageJSON?.version || "0.0.0");

        try {
          const check = await checkForWorkbenchUpdate(state.apiClient, currentVersion);
          if (!check.hasUpdate) {
            if (!silent) {
              vscode.window.showInformationMessage(
                `SailZen Workbench v${currentVersion} is already up to date (cloud latest: v${check.release.version}).`
              );
            }
            return;
          }

          const notesSuffix = check.release.release_notes
            ? ` — ${check.release.release_notes}`
            : "";
          const choice = await vscode.window.showInformationMessage(
            `SailZen Workbench v${check.release.version} is available (current v${currentVersion})${notesSuffix}`,
            "Update & Reload",
            "Later"
          );
          if (choice !== "Update & Reload") return;

          await vscode.window.withProgress(
            {
              location: vscode.ProgressLocation.Notification,
              title: `SailZen: Downloading & installing v${check.release.version}...`,
              cancellable: false,
            },
            async () => {
              const tmpVsix = await downloadAndVerifyVsix(state.apiClient, check.release);
              try {
                await vscode.commands.executeCommand(
                  "workbench.extensions.installExtension",
                  vscode.Uri.file(tmpVsix)
                );
              } finally {
                await fs.promises.unlink(tmpVsix).catch(() => {});
              }
            }
          );

          const reload = await vscode.window.showInformationMessage(
            `SailZen Workbench v${check.release.version} installed! Reload VS Code to activate?`,
            "Reload Now",
            "Later"
          );
          if (reload === "Reload Now") {
            await vscode.commands.executeCommand("workbench.action.reloadWindow");
          }
        } catch (err) {
          if (!silent) {
            const msg = err instanceof Error ? err.message : String(err);
            vscode.window.showWarningMessage(`SailZen OTA update check failed: ${msg}`);
          }
        }
      }
    )
  );

  // 34. Open ~/.sailzen/machine.json
  context.subscriptions.push(
    vscode.commands.registerCommand("sailzen.openMachineConfig", async () => {
      await state.registry.ensureConfigFileExists();
      const doc = await vscode.workspace.openTextDocument(
        vscode.Uri.file(state.registry.configPath)
      );
      await vscode.window.showTextDocument(doc, { preview: false });
    })
  );

  // 35. Workbench Diagnostics
  context.subscriptions.push(
    vscode.commands.registerCommand("sailzen.showDiagnostics", async () => {
      const stats = state.vaultIndex?.stats;
      const extVersion = String(context.extension.packageJSON?.version || "unknown");
      const lines = [
        `# SailZen Workbench Diagnostics`,
        `- Extension Version: v${extVersion}`,
        `- Machine ID: ${state.registry.current.machineId}`,
        `- Config Path: ${state.registry.configPath}`,
        `- Active Vault Role: ${state.activeVaultRole}`,
        `- Active Vault Root: ${state.activeVaultRoot || "(none)"}`,
        `- Work Offline Active: ${state.privacyGuard.isWorkOfflineActive()}`,
        `- Indexed Notes: ${stats ? `${stats.totalNotes} (${stats.durationMs}ms, cacheHits=${stats.cacheHits})` : "0"}`,
        `- Server URL: ${state.registry.current.serverUrl}`,
        `- Server Online: ${state.isOnline} ${state.lastServerError ? `(${state.lastServerError})` : ""}`,
        `- Loaded Works: ${state.works.length} | Topics: ${state.bootstrapData?.topics.length ?? 0}`,
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
