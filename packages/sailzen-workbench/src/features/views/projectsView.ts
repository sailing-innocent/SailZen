import * as vscode from "vscode";
import { AffairDTO, ContentTopicDTO, WorkbenchProjectItemDTO } from "../../core/server/types";
import { WorkbenchState } from "../../core/workbenchState";

type ProjectNodeKind = "project" | "milestone" | "namespace" | "topic" | "info";

export class ProjectTreeItem extends vscode.TreeItem {
  constructor(
    label: string,
    public readonly kind: ProjectNodeKind,
    collapsible: vscode.TreeItemCollapsibleState = vscode.TreeItemCollapsibleState.None,
    public readonly payload?: WorkbenchProjectItemDTO | AffairDTO | ContentTopicDTO | string
  ) {
    super(label, collapsible);
    if (kind === "project") this.contextValue = "ventureProject";
    if (kind === "milestone") this.contextValue = "ventureMilestone";
  }
}

function archetypeIcon(archetype: string): string {
  switch (archetype) {
    case "novel":
      return "book";
    case "game":
      return "game";
    case "research":
      return "beaker";
    case "engineering":
      return "circuit-board";
    default:
      return "rocket";
  }
}

export class ProjectsTreeDataProvider implements vscode.TreeDataProvider<ProjectTreeItem> {
  private readonly _onDidChangeTreeData = new vscode.EventEmitter<ProjectTreeItem | undefined>();
  public readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

  constructor(private readonly state: WorkbenchState) {
    this.state.onDidServerDataChange(() => this.refresh());
    this.state.onDidContextChange(() => this.refresh());
  }

  refresh(): void {
    this._onDidChangeTreeData.fire(undefined);
  }

  getTreeItem(element: ProjectTreeItem): vscode.TreeItem {
    return element;
  }

  getChildren(element?: ProjectTreeItem): ProjectTreeItem[] {
    if (this.state.privacyGuard.isWorkOfflineActive()) {
      if (element) return [];
      const item = new ProjectTreeItem("Offline Work Mode", "info");
      item.iconPath = new vscode.ThemeIcon("lock");
      return [item];
    }

    const boot = this.state.bootstrapData;
    if (!boot) {
      if (element) return [];
      const item = new ProjectTreeItem("Connect to sail_server to view Ventures & Topics", "info");
      item.iconPath = new vscode.ThemeIcon("cloud-offline");
      return [item];
    }

    if (!element) {
      const items: ProjectTreeItem[] = [];
      const activeSlug = this.state.activeProject?.workbench.slug;

      for (const proj of boot.projects) {
        const isCurrent = proj.workbench.slug === activeSlug;
        const days = proj.progress.days_left !== null ? `D-${proj.progress.days_left}` : "ongoing";
        const pct = Math.round(proj.progress.completion_ratio * 100);
        const boundPath = this.state.registry.resolveProjectPath(proj.workbench.slug);

        const item = new ProjectTreeItem(
          isCurrent ? `★ ${proj.progress.title}` : proj.progress.title,
          "project",
          isCurrent
            ? vscode.TreeItemCollapsibleState.Expanded
            : vscode.TreeItemCollapsibleState.Collapsed,
          proj
        );
        item.description = `${days} · ${pct}%${boundPath ? " · local" : ""}`;
        item.tooltip = [
          `Slug: ${proj.workbench.slug} (${proj.workbench.archetype})`,
          `14d focus: ${proj.progress.recent_14d_hours.toFixed(1)}h`,
          proj.workbench.vault_namespace ? `Vault: ${proj.workbench.vault_namespace}.*` : "",
          boundPath ? `Local path: ${boundPath}` : "Not bound on this machine",
        ]
          .filter(Boolean)
          .join("\n");
        item.iconPath = new vscode.ThemeIcon(archetypeIcon(proj.workbench.archetype));
        items.push(item);
      }

      if (items.length === 0) {
        const empty = new ProjectTreeItem("No active Ventures yet", "info");
        empty.iconPath = new vscode.ThemeIcon("info");
        items.push(empty);
      }
      return items;
    }

    if (element.kind === "project" && element.payload && typeof element.payload === "object") {
      const proj = element.payload as WorkbenchProjectItemDTO;
      const children: ProjectTreeItem[] = [];

      // Vault namespace quick jump
      if (proj.workbench.vault_namespace) {
        const nsItem = new ProjectTreeItem(
          `Notes: ${proj.workbench.vault_namespace}.*`,
          "namespace",
          vscode.TreeItemCollapsibleState.None,
          proj.workbench.vault_namespace
        );
        nsItem.iconPath = new vscode.ThemeIcon("folder-library");
        nsItem.command = {
          command: "sailzen.lookupNote",
          title: "Lookup in Namespace",
          arguments: [`${proj.workbench.vault_namespace}.`],
        };
        children.push(nsItem);
      }

      // Linked Content Topic
      if (proj.workbench.topic_id) {
        const topic = boot.topics.find((t) => t.id === proj.workbench.topic_id);
        if (topic) {
          const tItem = new ProjectTreeItem(
            `Topic: ${topic.title}`,
            "topic",
            vscode.TreeItemCollapsibleState.None,
            topic
          );
          tItem.description = topic.pillar;
          tItem.iconPath = new vscode.ThemeIcon("library");
          children.push(tItem);
        }
      }

      // Milestones
      for (const ms of proj.progress.milestones) {
        const isDone = ms.state === "DONE" || ms.state === "COMPLETED";
        const mItem = new ProjectTreeItem(
          ms.title,
          "milestone",
          vscode.TreeItemCollapsibleState.None,
          ms
        );
        mItem.description = isDone ? "DONE" : ms.urgency_ddl ? ms.urgency_ddl.slice(0, 10) : "";
        mItem.iconPath = new vscode.ThemeIcon(
          isDone ? "pass-filled" : "circle-outline",
          isDone ? new vscode.ThemeColor("testing.iconPassed") : undefined
        );
        children.push(mItem);
      }

      return children;
    }

    return [];
  }
}
