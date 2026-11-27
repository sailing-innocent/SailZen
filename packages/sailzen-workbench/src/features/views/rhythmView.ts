import * as vscode from "vscode";
import { AffairDTO, TicketDTO, TimeBlockDTO } from "../../core/server/types";
import { WorkbenchState } from "../../core/workbenchState";

type RhythmNodeKind = "header" | "section" | "block" | "affair" | "ticket" | "info";

export class RhythmTreeItem extends vscode.TreeItem {
  constructor(
    label: string,
    public readonly kind: RhythmNodeKind,
    collapsible: vscode.TreeItemCollapsibleState = vscode.TreeItemCollapsibleState.None,
    public readonly payload?: TimeBlockDTO | AffairDTO | TicketDTO | string
  ) {
    super(label, collapsible);
    if (kind === "block") {
      this.contextValue = "rhythmBlock";
    }
  }
}

function formatHHMM(iso: string): string {
  const m = iso.match(/T(\d{2}:\d{2})/);
  return m ? m[1] : iso.slice(11, 16);
}

function blockIcon(status: TimeBlockDTO["status"]): vscode.ThemeIcon {
  switch (status) {
    case "DONE":
      return new vscode.ThemeIcon("pass-filled", new vscode.ThemeColor("testing.iconPassed"));
    case "DOING":
      return new vscode.ThemeIcon("play-circle", new vscode.ThemeColor("charts.blue"));
    case "SKIPPED":
      return new vscode.ThemeIcon("circle-slash", new vscode.ThemeColor("disabledForeground"));
    default:
      return new vscode.ThemeIcon("circle-outline");
  }
}

export class RhythmTreeDataProvider implements vscode.TreeDataProvider<RhythmTreeItem> {
  private readonly _onDidChangeTreeData = new vscode.EventEmitter<RhythmTreeItem | undefined>();
  public readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

  constructor(private readonly state: WorkbenchState) {
    this.state.onDidServerDataChange(() => this.refresh());
    this.state.onDidContextChange(() => this.refresh());
  }

  refresh(): void {
    this._onDidChangeTreeData.fire(undefined);
  }

  getTreeItem(element: RhythmTreeItem): vscode.TreeItem {
    return element;
  }

  getChildren(element?: RhythmTreeItem): RhythmTreeItem[] {
    if (this.state.privacyGuard.isWorkOfflineActive()) {
      if (element) return [];
      const item = new RhythmTreeItem(
        "Work Vault Offline Mode",
        "info",
        vscode.TreeItemCollapsibleState.None
      );
      item.description = "Cloud sync blocked";
      item.iconPath = new vscode.ThemeIcon("lock");
      return [item];
    }

    const boot = this.state.bootstrapData;
    if (!boot) {
      if (element) return [];
      const item = new RhythmTreeItem(
        this.state.isOnline ? "Loading Rhythm..." : "Server Offline",
        "info",
        vscode.TreeItemCollapsibleState.None
      );
      item.description = this.state.lastServerError ? "Click refresh to retry" : "";
      item.iconPath = new vscode.ThemeIcon("cloud-offline");
      item.command = { command: "sailzen.refreshRhythm", title: "Refresh" };
      return [item];
    }

    if (!element) {
      const roots: RhythmTreeItem[] = [];
      const activeBlocks = boot.timeline.blocks.filter((b) => b.status !== "MOVED");

      const timelineSec = new RhythmTreeItem(
        `Timeline (${boot.date})`,
        "section",
        vscode.TreeItemCollapsibleState.Expanded,
        "timeline"
      );
      timelineSec.description = `${boot.timeline.completed_minutes}m / ${boot.timeline.planned_minutes}m (${activeBlocks.length})`;
      timelineSec.tooltip = boot.timeline.ai_rationale || "Today's Rhythm timeline";
      timelineSec.iconPath = new vscode.ThemeIcon("clock");
      roots.push(timelineSec);

      if (boot.focus_affairs.length > 0) {
        const focusSec = new RhythmTreeItem(
          `Focus Tasks (${boot.focus_affairs.length})`,
          "section",
          vscode.TreeItemCollapsibleState.Collapsed,
          "focus"
        );
        focusSec.iconPath = new vscode.ThemeIcon("target");
        roots.push(focusSec);
      }

      if (boot.pending_tickets.length > 0) {
        const ticketSec = new RhythmTreeItem(
          `SailTick Tickets (${boot.pending_tickets.length})`,
          "section",
          vscode.TreeItemCollapsibleState.Expanded,
          "tickets"
        );
        ticketSec.iconPath = new vscode.ThemeIcon("bell-dot");
        roots.push(ticketSec);
      }

      return roots;
    }

    if (element.kind === "section" && element.payload === "timeline") {
      const blocks = boot.timeline.blocks.filter((b) => b.status !== "MOVED");
      if (blocks.length === 0) {
        const empty = new RhythmTreeItem("No time blocks planned today", "info");
        empty.iconPath = new vscode.ThemeIcon("info");
        return [empty];
      }
      return blocks.map((blk) => {
        const title =
          blk.affair_title ||
          (typeof blk.ref?.label === "string" ? blk.ref.label : "") ||
          blk.block_type;
        const item = new RhythmTreeItem(
          `${formatHHMM(blk.start_time)}-${formatHHMM(blk.end_time)}  ${title}`,
          "block",
          vscode.TreeItemCollapsibleState.None,
          blk
        );
        item.description = blk.pinned ? "📌" : blk.status;
        item.iconPath = blockIcon(blk.status);
        item.command = {
          command: "sailzen.blockSetStatus",
          title: "Set Status",
          arguments: [item],
        };
        return item;
      });
    }

    if (element.kind === "section" && element.payload === "focus") {
      return boot.focus_affairs.map((a) => {
        const item = new RhythmTreeItem(a.title, "affair", vscode.TreeItemCollapsibleState.None, a);
        item.description = a.state;
        item.iconPath = new vscode.ThemeIcon("tasklist");
        return item;
      });
    }

    if (element.kind === "section" && element.payload === "tickets") {
      return boot.pending_tickets.map((t) => {
        const item = new RhythmTreeItem(
          t.title || t.body.slice(0, 40),
          "ticket",
          vscode.TreeItemCollapsibleState.None,
          t
        );
        item.description = t.priority;
        item.tooltip = t.body;
        item.iconPath = new vscode.ThemeIcon("comment-discussion");
        return item;
      });
    }

    return [];
  }
}
