import * as vscode from "vscode";
import {
  SAILZEN_VFS_SCHEME,
  SailZenVirtualDocumentProvider,
} from "./core/server/virtualFs";
import { WorkbenchState } from "./core/workbenchState";
import { registerWorkbenchCommands } from "./features/commands/registerCommands";
import { SailZenEditorProviders } from "./features/editor/wikilinkProvider";
import { CalendarWebviewProvider } from "./features/views/calendarView";
import { ProjectsTreeDataProvider } from "./features/views/projectsView";
import { QuickChatWebviewProvider } from "./features/views/quickChatView";
import { RhythmTreeDataProvider } from "./features/views/rhythmView";
import { WorkbenchStatusBar } from "./features/views/statusBar";
import { VaultTreeDataProvider } from "./features/views/vaultTreeView";

export async function activate(context: vscode.ExtensionContext): Promise<void> {
  const output = vscode.window.createOutputChannel("SailZen Workbench");
  const state = new WorkbenchState(output);
  context.subscriptions.push(output, state);

  // 1. Register sailzen:// Virtual FS (read-only cloud books/papers/clips/NoteItems/Topics)
  const vfsProvider = new SailZenVirtualDocumentProvider(state);
  context.subscriptions.push(
    vscode.workspace.registerTextDocumentContentProvider(SAILZEN_VFS_SCHEME, vfsProvider)
  );

  // 2. Register native TreeViews & minimal Webviews immediately (zero cold-start block)
  const rhythmProvider = new RhythmTreeDataProvider(state);
  const projectsProvider = new ProjectsTreeDataProvider(state);
  const vaultTreeProvider = new VaultTreeDataProvider(state);
  const calendarProvider = new CalendarWebviewProvider(state);
  const quickChatProvider = new QuickChatWebviewProvider(state);

  context.subscriptions.push(
    vscode.window.registerTreeDataProvider("sailzen.rhythmView", rhythmProvider),
    vscode.window.registerTreeDataProvider("sailzen.projectsView", projectsProvider),
    vscode.window.registerTreeDataProvider("sailzen.vaultTreeView", vaultTreeProvider),
    vscode.window.registerWebviewViewProvider(CalendarWebviewProvider.viewId, calendarProvider),
    vscode.window.registerWebviewViewProvider(QuickChatWebviewProvider.viewId, quickChatProvider),
    new WorkbenchStatusBar(state)
  );

  // 3. Register Editor Providers ([[wikilink]] completion/jump/hover + repo:// links)
  new SailZenEditorProviders(state).register(context);

  // 4. Register Workbench Commands
  registerWorkbenchCommands(context, state);

  // 5. Kick off warm cache load + incremental disk sync + async server bootstrap
  await state.initialize();
}

export function deactivate(): void {
  // All resources cleaned up via context.subscriptions
}
