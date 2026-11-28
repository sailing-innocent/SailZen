import * as vscode from "vscode";
import {
  AffairDTO,
  ContentTopicDTO,
  EditionTocDTO,
  NoteItemDTO,
  TocChapterDTO,
  TocVolumeDTO,
  WorkbenchProjectItemDTO,
  WorkDTO,
} from "../../core/server/types";
import { SailZenVfsUri } from "../../core/server/virtualFs";
import { WorkbenchState } from "../../core/workbenchState";

type ProjectNodeKind =
  | "section"
  | "project"
  | "milestone"
  | "namespace"
  | "topic"
  | "work"
  | "workSection"
  | "volume"
  | "chapter"
  | "noteItem"
  | "info";

export interface WorkSectionPayload {
  work: WorkDTO;
  section: "toc" | "notes";
}

export interface VolumePayload {
  workId: number;
  volume: TocVolumeDTO;
}

export interface ChapterPayload {
  workId: number;
  chapter: TocChapterDTO;
}

export class ProjectTreeItem extends vscode.TreeItem {
  constructor(
    label: string,
    public readonly kind: ProjectNodeKind,
    collapsible: vscode.TreeItemCollapsibleState = vscode.TreeItemCollapsibleState.None,
    public readonly payload?:
      | WorkbenchProjectItemDTO
      | AffairDTO
      | ContentTopicDTO
      | WorkDTO
      | WorkSectionPayload
      | VolumePayload
      | ChapterPayload
      | NoteItemDTO
      | string
  ) {
    super(label, collapsible);
    if (kind === "project") this.contextValue = "ventureProject";
    if (kind === "milestone") this.contextValue = "ventureMilestone";
    if (kind === "topic") this.contextValue = "contentTopic";
    if (kind === "work") this.contextValue = "contentWork";
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

function workStatusWeight(w: WorkDTO): number {
  if (w.is_original) return 0;
  if (w.reading_status === "reading") return 1;
  if (w.reading_status === "queued") return 2;
  if (w.reading_status === "paused") return 3;
  if (w.reading_status === "finished") return 4;
  return 5;
}

export class ProjectsTreeDataProvider implements vscode.TreeDataProvider<ProjectTreeItem> {
  private readonly _onDidChangeTreeData = new vscode.EventEmitter<ProjectTreeItem | undefined>();
  public readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

  private tocCache = new Map<number, EditionTocDTO>();
  private noteItemCache = new Map<number, NoteItemDTO[]>();

  constructor(private readonly state: WorkbenchState) {
    this.state.onDidServerDataChange(() => {
      this.tocCache.clear();
      this.noteItemCache.clear();
      this.refresh();
    });
    this.state.onDidContextChange(() => this.refresh());
  }

  refresh(): void {
    this._onDidChangeTreeData.fire(undefined);
  }

  getTreeItem(element: ProjectTreeItem): vscode.TreeItem {
    return element;
  }

  async getChildren(element?: ProjectTreeItem): Promise<ProjectTreeItem[]> {
    if (this.state.privacyGuard.isWorkOfflineActive()) {
      if (element) return [];
      const item = new ProjectTreeItem("Offline Work Mode", "info");
      item.iconPath = new vscode.ThemeIcon("lock");
      return [item];
    }

    const boot = this.state.bootstrapData;
    if (!boot) {
      if (element) return [];
      const item = new ProjectTreeItem("Connect to sail_server to view Ventures & Content", "info");
      item.iconPath = new vscode.ThemeIcon("cloud-offline");
      item.command = { command: "sailzen.refreshRhythm", title: "Refresh" };
      return [item];
    }

    // Root sections: Ventures | Topics | Reading & Creation Library
    if (!element) {
      const sections: ProjectTreeItem[] = [];

      const venturesSec = new ProjectTreeItem(
        `Ventures (${boot.projects.length})`,
        "section",
        vscode.TreeItemCollapsibleState.Expanded,
        "ventures"
      );
      venturesSec.iconPath = new vscode.ThemeIcon("rocket");
      sections.push(venturesSec);

      if (boot.topics.length > 0) {
        const topicsSec = new ProjectTreeItem(
          `Content Topics (${boot.topics.length})`,
          "section",
          vscode.TreeItemCollapsibleState.Collapsed,
          "topics"
        );
        topicsSec.iconPath = new vscode.ThemeIcon("library");
        sections.push(topicsSec);
      }

      if (this.state.works.length > 0) {
        const worksSec = new ProjectTreeItem(
          `Library & Works (${this.state.works.length})`,
          "section",
          vscode.TreeItemCollapsibleState.Collapsed,
          "works"
        );
        worksSec.iconPath = new vscode.ThemeIcon("book");
        sections.push(worksSec);
      }

      return sections;
    }

    // Section: Ventures
    if (element.kind === "section" && element.payload === "ventures") {
      if (boot.projects.length === 0) {
        const empty = new ProjectTreeItem("No active Ventures yet", "info");
        empty.iconPath = new vscode.ThemeIcon("info");
        return [empty];
      }
      const activeSlug = this.state.activeProject?.workbench.slug;
      return boot.projects.map((proj) => {
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
        return item;
      });
    }

    // Section: Topics
    if (element.kind === "section" && element.payload === "topics") {
      return boot.topics.map((topic) => this.buildTopicItem(topic));
    }

    // Section: Works
    if (element.kind === "section" && element.payload === "works") {
      const sorted = [...this.state.works].sort(
        (a, b) => workStatusWeight(a) - workStatusWeight(b) || a.title.localeCompare(b.title)
      );
      return sorted.map((w) => this.buildWorkItem(w));
    }

    // Project children
    if (element.kind === "project" && element.payload && typeof element.payload === "object") {
      const proj = element.payload as WorkbenchProjectItemDTO;
      const children: ProjectTreeItem[] = [];

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

      if (proj.workbench.topic_id) {
        const topic = boot.topics.find((t) => t.id === proj.workbench.topic_id);
        if (topic) {
          children.push(this.buildTopicItem(topic));
        }
      }

      if (proj.workbench.original_work_id) {
        const work = this.state.works.find((w) => w.id === proj.workbench.original_work_id);
        if (work) {
          children.push(this.buildWorkItem(work));
        }
      }

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

    // Topic children: lazy-load attached works + virtual overview link
    if (element.kind === "topic" && element.payload && typeof element.payload === "object") {
      const topic = element.payload as ContentTopicDTO;
      const children: ProjectTreeItem[] = [];
      const overview = new ProjectTreeItem("Open Topic Overview (Virtual)", "info");
      overview.iconPath = new vscode.ThemeIcon("preview");
      overview.command = {
        command: "sailzen.openVirtualUri",
        title: "Open Topic Overview",
        arguments: [SailZenVfsUri.topic(topic.id, topic.slug)],
      };
      children.push(overview);

      try {
        const detail = await this.state.apiClient.getTopicDetail(topic.id);
        for (const item of detail.works) {
          children.push(this.buildWorkItem(item.work));
        }
      } catch {
        children.push(new ProjectTreeItem("Failed to load topic works", "info"));
      }
      return children;
    }

    // Work children: Clips (Virtual) + TOC + NoteItems
    if (element.kind === "work" && element.payload && typeof element.payload === "object") {
      const work = element.payload as WorkDTO;
      const clipsItem = new ProjectTreeItem("Clips & Highlights (Virtual)", "info");
      clipsItem.iconPath = new vscode.ThemeIcon("quote");
      clipsItem.command = {
        command: "sailzen.openVirtualUri",
        title: "Open Clips",
        arguments: [SailZenVfsUri.clips(work.id, work.vault_slug || work.slug)],
      };

      const tocSec = new ProjectTreeItem(
        "Chapters & Volumes",
        "workSection",
        vscode.TreeItemCollapsibleState.Collapsed,
        { work, section: "toc" } satisfies WorkSectionPayload
      );
      tocSec.iconPath = new vscode.ThemeIcon("list-tree");

      const notesSec = new ProjectTreeItem(
        "NoteItems / Story Bible",
        "workSection",
        vscode.TreeItemCollapsibleState.Collapsed,
        { work, section: "notes" } satisfies WorkSectionPayload
      );
      notesSec.iconPath = new vscode.ThemeIcon("symbol-namespace");

      return [clipsItem, tocSec, notesSec];
    }

    // WorkSection: TOC or NoteItems
    if (element.kind === "workSection" && element.payload && typeof element.payload === "object") {
      const { work, section } = element.payload as WorkSectionPayload;
      if (section === "toc") {
        const toc = await this.loadWorkToc(work.id);
        if (!toc) {
          return [new ProjectTreeItem("No editions / chapters yet", "info")];
        }
        const items: ProjectTreeItem[] = [];
        for (const vol of toc.volumes) {
          const vLabel = [vol.label, vol.title].filter(Boolean).join(" ").trim();
          const vItem = new ProjectTreeItem(
            vLabel,
            "volume",
            vscode.TreeItemCollapsibleState.Collapsed,
            { workId: work.id, volume: vol } satisfies VolumePayload
          );
          vItem.description = `${vol.chapter_count} ch`;
          vItem.iconPath = new vscode.ThemeIcon("folder");
          items.push(vItem);
        }
        for (const ch of toc.ungrouped_chapters.slice(0, 200)) {
          items.push(this.buildChapterItem(work.id, ch));
        }
        if (toc.ungrouped_chapters.length > 200) {
          items.push(
            new ProjectTreeItem(
              `... +${toc.ungrouped_chapters.length - 200} more chapters`,
              "info"
            )
          );
        }
        return items.length > 0 ? items : [new ProjectTreeItem("Empty TOC", "info")];
      }

      if (section === "notes") {
        let notes = this.noteItemCache.get(work.id);
        if (!notes) {
          try {
            const res = await this.state.apiClient.listNoteItems({ work_id: work.id, limit: 100 });
            notes = res.notes;
            this.noteItemCache.set(work.id, notes);
          } catch {
            return [new ProjectTreeItem("Failed to load NoteItems", "info")];
          }
        }
        if (notes.length === 0) {
          return [new ProjectTreeItem("No NoteItems yet", "info")];
        }
        return notes.map((ni) => {
          const title = ni.title || ni.slug || `NoteItem #${ni.id}`;
          const item = new ProjectTreeItem(
            title,
            "noteItem",
            vscode.TreeItemCollapsibleState.None,
            ni
          );
          item.description = ni.category;
          item.iconPath = new vscode.ThemeIcon("note");
          item.command = {
            command: "sailzen.openVirtualUri",
            title: "Open NoteItem",
            arguments: [SailZenVfsUri.noteItem(ni.id, title)],
          };
          return item;
        });
      }
    }

    // Volume children: Chapters
    if (element.kind === "volume" && element.payload && typeof element.payload === "object") {
      const { workId, volume } = element.payload as VolumePayload;
      return volume.chapters.map((ch) => this.buildChapterItem(workId, ch));
    }

    return [];
  }

  private buildTopicItem(topic: ContentTopicDTO): ProjectTreeItem {
    const tItem = new ProjectTreeItem(
      topic.title,
      "topic",
      vscode.TreeItemCollapsibleState.Collapsed,
      topic
    );
    tItem.description = `${topic.pillar}${topic.work_count ? ` · ${topic.work_count} works` : ""}`;
    tItem.tooltip = topic.description || topic.title;
    tItem.iconPath = new vscode.ThemeIcon("library");
    return tItem;
  }

  private buildWorkItem(work: WorkDTO): ProjectTreeItem {
    const pct = work.progress_pct != null ? `${Math.round(work.progress_pct)}%` : "";
    const tag = work.is_original ? "✍ " : "";
    const item = new ProjectTreeItem(
      `${tag}${work.title}`,
      "work",
      vscode.TreeItemCollapsibleState.Collapsed,
      work
    );
    item.description = [work.pillar, work.reading_status, pct].filter(Boolean).join(" · ");
    item.tooltip = [
      work.title,
      work.author ? `Author: ${work.author}` : "",
      `Type: ${work.work_type} | Status: ${work.reading_status}`,
      work.vault_slug ? `Vault slug: read.${work.vault_slug}` : "",
    ]
      .filter(Boolean)
      .join("\n");
    item.iconPath = new vscode.ThemeIcon(work.is_original ? "edit" : "book");
    return item;
  }

  private buildChapterItem(workId: number, ch: TocChapterDTO): ProjectTreeItem {
    const label = [ch.label, ch.title].filter(Boolean).join(" ").trim() || `Chapter ${ch.sort_index + 1}`;
    const item = new ProjectTreeItem(
      label,
      "chapter",
      vscode.TreeItemCollapsibleState.None,
      { workId, chapter: ch } satisfies ChapterPayload
    );
    item.description = ch.char_count ? `${ch.char_count} chars` : undefined;
    item.iconPath = new vscode.ThemeIcon("file-text");
    item.command = {
      command: "sailzen.openVirtualUri",
      title: "Read Chapter (Virtual)",
      arguments: [SailZenVfsUri.chapter(workId, ch.id, label)],
    };
    return item;
  }

  private async loadWorkToc(workId: number): Promise<EditionTocDTO | null> {
    const cached = this.tocCache.get(workId);
    if (cached) return cached;
    try {
      const editions = await this.state.apiClient.getEditionsByWork(workId);
      if (editions.length === 0) return null;
      const canonical = editions.find((e) => e.canonical) || editions[0];
      const toc = await this.state.apiClient.getEditionToc(canonical.id);
      this.tocCache.set(workId, toc);
      return toc;
    } catch {
      return null;
    }
  }
}
