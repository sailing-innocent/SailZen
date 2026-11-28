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

    // Lowercase stable ID ensures TreeView.reveal() matches reliably on Windows/macOS/Linux
    this.id = node.fname.toLowerCase();
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

  private readonly itemCache = new Map<string, VaultTreeItem>();

  constructor(private readonly state: WorkbenchState) {
    this.state.onDidVaultChange(() => this.refresh());
  }

  refresh(): void {
    this.itemCache.clear();
    this._onDidChangeTreeData.fire(undefined);
  }

  getEffectiveRootNamespace(): string {
    return this.state.treeProjectFilter && this.state.activeProject?.workbench.vault_namespace
      ? this.state.activeProject.workbench.vault_namespace
      : "";
  }

  private toTreeItem(node: HierarchyChildItem): VaultTreeItem {
    const key = node.fname.toLowerCase();
    const cached = this.itemCache.get(key);
    if (cached && cached.node.hasChildren === node.hasChildren && cached.node.note === node.note) {
      return cached;
    }
    const item = new VaultTreeItem(node);
    this.itemCache.set(key, item);
    return item;
  }

  getTreeItem(element: VaultTreeItem): vscode.TreeItem {
    return element;
  }

  getChildren(element?: VaultTreeItem): VaultTreeItem[] {
    const index = this.state.vaultIndex;
    if (!index) return [];

    if (!element) {
      const ns = this.getEffectiveRootNamespace();
      return index.getChildren(ns).map((child) => this.toTreeItem(child));
    }

    return index.getChildren(element.node.fname).map((child) => this.toTreeItem(child));
  }

  getParent(element: VaultTreeItem): VaultTreeItem | undefined {
    const index = this.state.vaultIndex;
    if (!index) return undefined;
    const ns = this.getEffectiveRootNamespace();
    const parentNode = index.getParentHierarchyNode(element.node.fname, ns);
    if (!parentNode) return undefined;
    return this.toTreeItem(parentNode);
  }

  getItemForFname(fname: string): VaultTreeItem | undefined {
    const index = this.state.vaultIndex;
    if (!index) return undefined;
    const ns = this.getEffectiveRootNamespace();
    if (!index.isUnderNamespace(fname, ns)) return undefined;
    const node = index.getHierarchyNode(fname);
    if (!node) return undefined;
    return this.toTreeItem(node);
  }
}

/**
 * Keeps VaultTree synchronized with the focused Markdown note (both Editor & Native Markdown Preview):
 * automatically reveals and expands the active note so its parent, siblings, and child pages are visible.
 */
export class VaultTreeLinkageController implements vscode.Disposable {
  private readonly disposables: vscode.Disposable[] = [];
  private debounceTimer: NodeJS.Timeout | null = null;
  private lastRevealedKey: string | null = null;

  constructor(
    private readonly treeView: vscode.TreeView<VaultTreeItem>,
    private readonly provider: VaultTreeDataProvider,
    private readonly state: WorkbenchState
  ) {
    const syncFromActiveTab = () => {
      const uri = this.state.resolveActiveFileUri();
      if (uri) {
        const fname = this.state.getNoteFnameForPath(uri.fsPath);
        if (fname) {
          this.state.setLastActiveVaultNoteFname(fname);
          this.scheduleAutoReveal(fname, false);
          return;
        }
      }

      const activeTab = vscode.window.tabGroups.activeTabGroup?.activeTab;
      if (activeTab?.label) {
        const m = activeTab.label.match(/^Preview\s+(.+?)\.md$/i);
        if (m) {
          const note = this.state.vaultIndex?.getNote(m[1].trim());
          if (note) {
            this.state.setLastActiveVaultNoteFname(note.fname);
            this.scheduleAutoReveal(note.fname, false);
          }
        }
      }
    };

    this.disposables.push(
      vscode.window.onDidChangeActiveTextEditor(() => syncFromActiveTab()),
      vscode.window.tabGroups.onDidChangeTabs(() => syncFromActiveTab()),
      vscode.window.tabGroups.onDidChangeTabGroups(() => syncFromActiveTab()),
      this.treeView.onDidChangeVisibility((e) => {
        if (e.visible) {
          const fname = this.state.resolveActiveVaultNoteFname();
          if (fname) {
            this.scheduleAutoReveal(fname, true);
          }
        }
      }),
      this.state.onDidVaultChange(() => {
        const fname = this.state.resolveActiveVaultNoteFname();
        if (fname && fname.toLowerCase() !== this.lastRevealedKey) {
          this.scheduleAutoReveal(fname, false);
        }
      })
    );

    // Initial sync if an editor or native Markdown custom editor tab is already open on startup
    const initial = this.state.resolveActiveVaultNoteFname();
    if (initial) {
      this.scheduleAutoReveal(initial, true);
    }
  }

  private isAutoRevealEnabled(): boolean {
    return vscode.workspace
      .getConfiguration("sailzen")
      .get<boolean>("vaultTree.autoReveal", true);
  }

  private scheduleAutoReveal(fname: string, forceSameKey: boolean): void {
    if (!this.isAutoRevealEnabled()) return;
    if (!this.treeView.visible) return;
    if (!forceSameKey && fname.toLowerCase() === this.lastRevealedKey) return;

    if (this.debounceTimer) {
      clearTimeout(this.debounceTimer);
    }
    this.debounceTimer = setTimeout(() => {
      this.debounceTimer = null;
      void this.revealFname(fname, { focus: false, force: false });
    }, 80);
  }

  /** Reveal the currently active vault note in VaultTree (also invoked manually by command). */
  async revealActiveNote(opts?: { focus?: boolean; force?: boolean }): Promise<boolean> {
    const fname = this.state.resolveActiveVaultNoteFname();
    if (!fname) return false;
    return this.revealFname(fname, {
      focus: opts?.focus ?? true,
      force: opts?.force ?? true,
    });
  }

  private async revealFname(
    fname: string,
    opts: { focus: boolean; force: boolean }
  ): Promise<boolean> {
    if (!opts.force && !this.treeView.visible) return false;

    const index = this.state.vaultIndex;
    if (!index) return false;

    // If an active tab points to a brand-new note not indexed yet, index it first
    if (!index.getNote(fname)) {
      const activeUri = this.state.resolveActiveFileUri();
      if (activeUri) {
        const editorFname = this.state.getNoteFnameForPath(activeUri.fsPath);
        if (editorFname && editorFname.toLowerCase() === fname.toLowerCase()) {
          await index.upsertFile(activeUri.fsPath);
          this.provider.refresh();
        }
      }
    }

    const item = this.provider.getItemForFname(fname);
    if (!item) return false;

    try {
      await this.treeView.reveal(item, {
        select: true,
        focus: opts.focus,
        expand: true,
      });
      this.lastRevealedKey = fname.toLowerCase();
      return true;
    } catch {
      // Tree may still be refreshing or filtered out; ignore silently
      return false;
    }
  }

  dispose(): void {
    if (this.debounceTimer) {
      clearTimeout(this.debounceTimer);
      this.debounceTimer = null;
    }
    for (const d of this.disposables) d.dispose();
  }
}
