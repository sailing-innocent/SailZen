/**
 * @file DocStatusBar.ts
 * @brief Status bar integration for SailZen Doc mode
 * @description Shows the current note's doc role and export format in the
 *   VSCode status bar. Clicking it opens the export command.
 */

import * as vscode from "vscode";
import { hasDocConfig, extractDocFrontmatter } from "@saili/common-all";
import { ExtensionProvider } from "../ExtensionProvider";

const FORMAT_ICONS: Record<string, string> = {
  latex: "$(file-code)",
  typst: "$(symbol-file)",
  slidev: "$(play)",
  markdown: "$(markdown)",
};

export class DocStatusBarProvider {
  private statusBarItem: vscode.StatusBarItem;
  private disposables: vscode.Disposable[] = [];

  constructor() {
    this.statusBarItem = vscode.window.createStatusBarItem(
      vscode.StatusBarAlignment.Right,
      100
    );
    this.statusBarItem.command = "sailzen.exportNote";
    this.statusBarItem.tooltip = "SailZen: Export this document";
  }

  activate(context: vscode.ExtensionContext): void {
    context.subscriptions.push(this.statusBarItem);

    // Update when active editor changes
    this.disposables.push(
      vscode.window.onDidChangeActiveTextEditor(() => this.update())
    );

    // Update when document is saved (frontmatter may have changed)
    this.disposables.push(
      vscode.workspace.onDidSaveTextDocument(() => this.update())
    );

    this.update();
  }

  private async update(): Promise<void> {
    const editor = vscode.window.activeTextEditor;
    if (!editor || editor.document.languageId !== "markdown") {
      this.statusBarItem.hide();
      return;
    }

    try {
      const note = await ExtensionProvider.getWSUtils().getNoteFromDocument(
        editor.document
      );
      if (!note || !hasDocConfig(note.custom)) {
        this.statusBarItem.hide();
        return;
      }

      const docFm = extractDocFrontmatter(note.custom);
      const role = docFm?.role || "source";
      const exports = docFm?.exports || [];
      const formats = exports.map((e: any) => e.format);
      const primaryFormat = formats[0] || "latex";
      const icon = FORMAT_ICONS[primaryFormat] || "$(file)";

      this.statusBarItem.text = `${icon} ${role}`;
      this.statusBarItem.tooltip =
        `SailZen Doc: ${note.fname}\n` +
        `Role: ${role}\n` +
        `Formats: ${formats.join(", ") || "latex"}\n` +
        `Click to export`;
      this.statusBarItem.show();
    } catch {
      this.statusBarItem.hide();
    }
  }

  dispose(): void {
    this.statusBarItem.dispose();
    for (const d of this.disposables) {
      d.dispose();
    }
  }
}
