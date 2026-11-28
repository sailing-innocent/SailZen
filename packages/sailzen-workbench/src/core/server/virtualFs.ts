import * as vscode from "vscode";
import { WorkbenchState } from "../workbenchState";

export const SAILZEN_VFS_SCHEME = "sailzen";

function sanitizeSlugSegment(raw: string): string {
  return (raw || "untitled")
    .replace(/[\\/:*?"<>|#%]+/g, "-")
    .replace(/\s+/g, "-")
    .slice(0, 60);
}

/** URI builders for read-only cloud Content 2.0 documents. */
export const SailZenVfsUri = {
  chapter(workId: number, nodeId: number, title: string): vscode.Uri {
    return vscode.Uri.parse(
      `${SAILZEN_VFS_SCHEME}:/work/${workId}/node/${nodeId}/${sanitizeSlugSegment(title)}.md`
    );
  },
  clips(workId: number, slug: string): vscode.Uri {
    return vscode.Uri.parse(
      `${SAILZEN_VFS_SCHEME}:/work/${workId}/clips/${sanitizeSlugSegment(slug)}.clips.md`
    );
  },
  noteItem(noteId: number, title: string): vscode.Uri {
    return vscode.Uri.parse(
      `${SAILZEN_VFS_SCHEME}:/note-item/${noteId}/${sanitizeSlugSegment(title)}.md`
    );
  },
  topic(topicId: number, slug: string): vscode.Uri {
    return vscode.Uri.parse(
      `${SAILZEN_VFS_SCHEME}:/topic/${topicId}/${sanitizeSlugSegment(slug)}.md`
    );
  },
};

/**
 * Read-only Virtual FileSystem provider for `sailzen://` cloud Content 2.0 resources.
 * Lets users read cloud books, papers, clips, NoteItems, and Topics natively in VS Code
 * without polluting local D:/vault or Git repositories.
 */
export class SailZenVirtualDocumentProvider
  implements vscode.TextDocumentContentProvider
{
  private readonly _onDidChange = new vscode.EventEmitter<vscode.Uri>();
  public readonly onDidChange = this._onDidChange.event;

  constructor(private readonly state: WorkbenchState) {}

  refresh(uri: vscode.Uri): void {
    this._onDidChange.fire(uri);
  }

  async provideTextDocumentContent(uri: vscode.Uri): Promise<string> {
    if (this.state.privacyGuard.isWorkOfflineActive()) {
      return `> 🔒 Work Vault offline mode is active. Cloud Content 2.0 virtual documents are disabled.\n`;
    }

    const p = uri.path;

    // 1. Chapter / DocumentNode: /work/{workId}/node/{nodeId}/{title}.md
    const nodeMatch = p.match(/^\/work\/(\d+)\/node\/(\d+)\//);
    if (nodeMatch) {
      const nodeId = Number(nodeMatch[2]);
      const node = await this.state.apiClient.getDocumentNode(nodeId);
      const heading = [node.label, node.title].filter(Boolean).join(" ").trim() || `Node #${node.id}`;
      const header = [
        `<!-- sailzen:// read-only cloud document (node_id=${node.id}, edition_id=${node.edition_id}) -->`,
        `# ${heading}`,
        "",
        `> 字数: ${node.word_count ?? "-"} · 字符: ${node.char_count ?? "-"} · 路径: \`${node.path ?? "-"}\``,
        "",
        "---",
        "",
      ].join("\n");
      return header + (node.raw_text || "*(空章节)*") + "\n";
    }

    // 2. Reading Clips: /work/{workId}/clips/{slug}.clips.md
    const clipsMatch = p.match(/^\/work\/(\d+)\/clips\//);
    if (clipsMatch) {
      const workId = Number(clipsMatch[1]);
      const exp = await this.state.apiClient.exportWorkClips(workId);
      return (
        `<!-- sailzen:// read-only clips (work_id=${workId}, annotations=${exp.annotation_count}) -->\n` +
        (exp.clips_markdown || `# ${exp.work_title} — Clips\n\n*(暂无划线/批注)*\n`)
      );
    }

    // 3. NoteItem (character / setting / outline / plot): /note-item/{noteId}/{title}.md
    const noteMatch = p.match(/^\/note-item\/(\d+)\//);
    if (noteMatch) {
      const noteId = Number(noteMatch[1]);
      const res = await this.state.apiClient.getNoteItemContent(noteId);
      return (
        `<!-- sailzen:// read-only NoteItem (id=${res.id}, file=${res.setting_file}) -->\n` +
        (res.content || `*(NoteItem #${res.id} 内容为空)*\n`)
      );
    }

    // 4. Content Topic Overview: /topic/{topicId}/{slug}.md
    const topicMatch = p.match(/^\/topic\/(\d+)\//);
    if (topicMatch) {
      const topicId = Number(topicMatch[1]);
      const detail = await this.state.apiClient.getTopicDetail(topicId);
      const lines: string[] = [
        `<!-- sailzen:// read-only Content Topic (id=${topicId}) -->`,
        `# Topic: ${detail.topic.title}`,
        "",
        `- **Slug**: \`${detail.topic.slug}\``,
        `- **Pillar**: \`${detail.topic.pillar}\` · **Status**: \`${detail.topic.status}\``,
      ];
      if (detail.venture) {
        lines.push(`- **Linked Venture**: ${detail.venture.title} (#${detail.venture.id}, ${detail.venture.state})`);
      }
      if (detail.topic.description) {
        lines.push("", "## Description", "", detail.topic.description);
      }
      lines.push("", "## Attached Works", "");
      if (detail.works.length === 0) {
        lines.push("- *(No works attached yet)*");
      } else {
        for (const item of detail.works) {
          const pct = item.work.progress_pct != null ? `${Math.round(item.work.progress_pct)}%` : "-";
          lines.push(
            `- [${item.work.reading_status}] **${item.work.title}** (${item.role}, pillar: ${item.work.pillar}, progress: ${pct})`
          );
        }
      }
      if (detail.rhythm_tasks.length > 0) {
        lines.push("", "## Linked Rhythm Tasks", "");
        for (const t of detail.rhythm_tasks) {
          const box = t.state === "DONE" || t.state === "COMPLETED" ? "x" : " ";
          lines.push(`- [${box}] #${t.id} ${t.title} (${t.state})`);
        }
      }
      return lines.join("\n") + "\n";
    }

    return `# SailZen Virtual Resource\n\nUnknown virtual URI: \`${uri.toString()}\`\n`;
  }
}
