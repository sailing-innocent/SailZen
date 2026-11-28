import * as vscode from "vscode";
import {
  SAILZEN_VFS_SCHEME,
  SailZenVirtualDocumentProvider,
} from "./core/server/virtualFs";
import { WorkbenchState } from "./core/workbenchState";
import { registerWorkbenchCommands } from "./features/commands/registerCommands";
import {
  extendMarkdownItWithSailZen,
  MarkdownItLike,
} from "./features/editor/markdownPreview";
import { SailZenEditorProviders } from "./features/editor/wikilinkProvider";
import { CalendarWebviewProvider } from "./features/views/calendarView";
import { ProjectsTreeDataProvider } from "./features/views/projectsView";
import { QuickChatWebviewProvider } from "./features/views/quickChatView";
import { RhythmTreeDataProvider } from "./features/views/rhythmView";
import { WorkbenchStatusBar } from "./features/views/statusBar";
import {
  VaultTreeDataProvider,
  VaultTreeLinkageController,
} from "./features/views/vaultTreeView";

export interface SailZenExtensionApi {
  extendMarkdownIt<T extends MarkdownItLike>(md: T): T;
}

export async function activate(
  context: vscode.ExtensionContext
): Promise<SailZenExtensionApi> {
  const output = vscode.window.createOutputChannel("SailZen Workbench");
  const state = new WorkbenchState(output);
  context.subscriptions.push(output, state);

  // 1. Register sailzen:// Virtual FS (read-only cloud books/papers/clips/NoteItems/Topics)
  const vfsProvider = new SailZenVirtualDocumentProvider(state);
  context.subscriptions.push(
    vscode.workspace.registerTextDocumentContentProvider(SAILZEN_VFS_SCHEME, vfsProvider)
  );

  // 2. Register native TreeViews & minimal Webviews across dual sidebars
  //    Left Activity Bar (sailzen-workbench): Vault Tree + Calendar
  //    Right Secondary Sidebar (sailzen-cloud): Today & Rhythm + SailTick QuickChat + Projects & Content
  const rhythmProvider = new RhythmTreeDataProvider(state);
  const projectsProvider = new ProjectsTreeDataProvider(state);
  const vaultTreeProvider = new VaultTreeDataProvider(state);
  const calendarProvider = new CalendarWebviewProvider(state);
  const quickChatProvider = new QuickChatWebviewProvider(state);

  const vaultTreeView = vscode.window.createTreeView("sailzen.vaultTreeView", {
    treeDataProvider: vaultTreeProvider,
    showCollapseAll: true,
  });
  const vaultTreeLinkage = new VaultTreeLinkageController(
    vaultTreeView,
    vaultTreeProvider,
    state
  );

  context.subscriptions.push(
    vaultTreeView,
    vaultTreeLinkage,
    vscode.window.registerTreeDataProvider("sailzen.rhythmView", rhythmProvider),
    vscode.window.registerTreeDataProvider("sailzen.projectsView", projectsProvider),
    vscode.window.registerWebviewViewProvider(CalendarWebviewProvider.viewId, calendarProvider),
    vscode.window.registerWebviewViewProvider(QuickChatWebviewProvider.viewId, quickChatProvider),
    new WorkbenchStatusBar(state)
  );

  // 3. Register Native Markdown Editor Providers (wikilink completion/jump/hover/backlinks/decorations)
  const editorProviders = new SailZenEditorProviders(state);
  editorProviders.register(context);

  // 4. Register Workbench Commands
  registerWorkbenchCommands(context, state, {
    editorProviders,
    vaultTreeLinkage,
  });

  // 5. Refresh any open native Markdown Preview once the vault index updates
  let previewRefreshTimer: NodeJS.Timeout | null = null;
  context.subscriptions.push(
    state.onDidVaultChange(() => {
      if (previewRefreshTimer) clearTimeout(previewRefreshTimer);
      previewRefreshTimer = setTimeout(() => {
        previewRefreshTimer = null;
        void Promise.resolve(
          vscode.commands.executeCommand("markdown.preview.refresh")
        ).catch(() => {});
      }, 200);
    }),
    {
      dispose: () => {
        if (previewRefreshTimer) {
          clearTimeout(previewRefreshTimer);
          previewRefreshTimer = null;
        }
      },
    }
  );

  // 6. Kick off warm cache load + incremental disk sync + async server bootstrap
  await state.initialize();

  // 7. Non-blocking OTA update check shortly after startup (skipped in Work Offline mode)
  const checkOnStartup = vscode.workspace
    .getConfiguration("sailzen")
    .get<boolean>("updater.checkOnStartup", true);
  if (checkOnStartup) {
    const otaTimer = setTimeout(() => {
      void vscode.commands.executeCommand("sailzen.checkForUpdate", { silent: true });
    }, 4500);
    context.subscriptions.push({ dispose: () => clearTimeout(otaTimer) });
  }

  // 8. Extend VS Code's built-in Native Markdown Previewer with [[wikilink]], ![[embed]], and repo:// support
  return {
    extendMarkdownIt<T extends MarkdownItLike>(md: T): T {
      return extendMarkdownItWithSailZen(md, {
        resolveNote: (target) => state.vaultIndex?.getNote(target),
        resolveRepoPath: (slug) => state.registry.resolveProjectPath(slug),
      });
    },
  };
}

export function deactivate(): void {
  // All resources cleaned up via context.subscriptions
}
