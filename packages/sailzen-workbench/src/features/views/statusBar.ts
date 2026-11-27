import * as vscode from "vscode";
import { WorkbenchState } from "../../core/workbenchState";

function countMixedWords(text: string): number {
  const cjk = (text.match(/[\u4e00-\u9fff]/g) || []).length;
  const latin = (text.match(/[A-Za-z0-9_]+/g) || []).length;
  return cjk + latin;
}

export class WorkbenchStatusBar implements vscode.Disposable {
  private readonly mainItem: vscode.StatusBarItem;
  private readonly wordCountItem: vscode.StatusBarItem;
  private readonly disposables: vscode.Disposable[] = [];

  constructor(private readonly state: WorkbenchState) {
    this.mainItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
    this.mainItem.command = "sailzen.switchVault";
    this.mainItem.show();

    this.wordCountItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 90);

    this.disposables.push(
      this.mainItem,
      this.wordCountItem,
      this.state.onDidContextChange(() => this.update()),
      this.state.onDidServerDataChange(() => this.update()),
      this.state.onDidVaultChange(() => this.update()),
      vscode.window.onDidChangeActiveTextEditor(() => this.updateWordCount()),
      vscode.workspace.onDidChangeTextDocument((e) => {
        if (vscode.window.activeTextEditor?.document === e.document) {
          this.updateWordCount();
        }
      })
    );

    this.update();
    this.updateWordCount();
  }

  update(): void {
    const isOfflineWork = this.state.privacyGuard.isWorkOfflineActive();
    const parts: string[] = [];

    if (isOfflineWork) {
      parts.push("$(lock) SailZen Work (Offline)");
    } else {
      const icon = this.state.isOnline ? "$(compass)" : "$(cloud-offline)";
      parts.push(`${icon} SailZen`);
    }

    if (this.state.activeProject) {
      parts.push(`[${this.state.activeProject.workbench.slug}]`);
    }

    // Show current DOING or next PLANNED block
    const boot = this.state.bootstrapData;
    if (!isOfflineWork && boot) {
      const active =
        boot.timeline.blocks.find((b) => b.status === "DOING") ||
        boot.timeline.blocks.find((b) => b.status === "PLANNED");
      if (active) {
        const label =
          active.affair_title ||
          (typeof active.ref?.label === "string" ? active.ref.label : "") ||
          active.block_type;
        const hhmm = active.start_time.slice(11, 16);
        parts.push(`${active.status === "DOING" ? "▶" : hhmm} ${label.slice(0, 22)}`);
      }
    }

    this.mainItem.text = parts.join(" · ");
    const noteCount = this.state.vaultIndex?.size ?? 0;
    this.mainItem.tooltip = [
      `Vault (${this.state.activeVaultRole}): ${this.state.activeVaultRoot || "unconfigured"} (${noteCount} notes)`,
      `Server: ${this.state.isOnline ? "online" : this.state.lastServerError || "offline"}`,
      "Click to switch vault (Private / Work)",
    ].join("\n");
  }

  private updateWordCount(): void {
    const editor = vscode.window.activeTextEditor;
    if (!editor || editor.document.languageId !== "markdown") {
      this.wordCountItem.hide();
      return;
    }
    const text = editor.document.getText();
    // Strip YAML frontmatter from word count
    const body = text.replace(/^---\r?\n[\s\S]*?\r?\n---\r?\n?/, "");
    const words = countMixedWords(body);
    this.wordCountItem.text = `$(edit) ${words} 字`;
    this.wordCountItem.tooltip = "SailZen Markdown Word Count (excluding frontmatter)";
    this.wordCountItem.show();
  }

  dispose(): void {
    for (const d of this.disposables) d.dispose();
  }
}
