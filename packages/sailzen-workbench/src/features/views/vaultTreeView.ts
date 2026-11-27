import * as vscode from "vscode";
import { HierarchyChildItem } from "../../core/vault/vaultIndex";
import { WorkbenchState } from "../../core/workbenchState";

export class VaultTreeItem extends vscode.TreeItem {
  constructor(public readonly node: HierarchyChildItem) {
    super(
      node.segment,
      node.hasChildren
        ? vscode.TreeItemCollapsibleState.Collapsed
        : vscode.TreeItemCollapsibleState.None
    );

    this.id = node.fname;
    this.tooltip = node.note
      ? `${node.note.title}\n${node.fname}`
      : `${node.fname} (virtual hierarchy node)`;

    if (node.note) {
      this.description =
        node.note.title.toLowerCase() !== node.segment.toLowerCase()
          ? node.note.title
          : undefined;
      this.iconPath = new vscode.ThemeIcon(node.hasChildren ? "book" : "markdown");
      this.contextValue = "vaultNote";
      this.command = {
        command: "vscode.open",
        title: "Open Note",
        arguments: [vscode.Uri.file(node.note.fsPath)],
      };
    } else {
      this.iconPath = new vscode.ThemeIcon("folder");
      this.contextValue = "vaultStub";
    }
  }
}

export class VaultTreeDataProvider implements vscode.TreeDataProvider<VaultTreeItem> {
  private readonly _onDidChangeTreeData = new vscode.EventEmitter<VaultTreeItem | undefined>();
  public readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

  constructor(private readonly state: WorkbenchState) {
    this.state.onDidVaultChange(() => this.refresh());
  }

  refresh(): void {
    this._onDidChangeTreeData.fire(undefined);
  }

  getTreeItem(element: VaultTreeItem): vscode.TreeItem {
    return element;
  }

  getChildren(element?: VaultTreeItem): VaultTreeItem[] {
    const index = this.state.vaultIndex;
    if (!index) return [];

    if (!element) {
      // Optional project namespace focus filter
      const ns =
        this.state.treeProjectFilter && this.state.activeProject?.workbench.vault_namespace
          ? this.state.activeProject.workbench.vault_namespace
          : "";
      return index.getChildren(ns).map((child) => new VaultTreeItem(child));
    }

    return index.getChildren(element.node.fname).map((child) => new VaultTreeItem(child));
  }
}
