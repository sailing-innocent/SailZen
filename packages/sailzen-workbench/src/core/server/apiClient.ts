import { MachineRegistry } from "../machine/machineConfig";
import { PrivacyGuard } from "../machine/privacyGuard";
import {
  AffairDTO,
  BlockStatus,
  ChapterSyncRequestDTO,
  ChapterSyncResponseDTO,
  ContentTopicDetailDTO,
  DocumentNodeDTO,
  EditionDTO,
  EditionTocDTO,
  NoteItemContentDTO,
  NoteItemListDTO,
  QuickChatResponseDTO,
  TimeBlockDTO,
  TopicRhythmTaskSummaryDTO,
  VaultNoteIndexItemDTO,
  VaultNoteIndexSyncResponseDTO,
  WorkClipsExportDTO,
  WorkbenchBootstrapDTO,
  WorkbenchContextPackDTO,
  WorkbenchProjectItemDTO,
  WorkbenchProjectMetaDTO,
  WorkbenchReleaseInfoDTO,
  WorkDTO,
} from "./types";

export class ServerOfflineError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ServerOfflineError";
  }
}

export class SailZenApiClient {
  constructor(
    private readonly registry: MachineRegistry,
    private readonly privacyGuard: PrivacyGuard,
    private readonly timeoutMs = 15000
  ) {}

  private getBaseUrl(): string {
    const raw = (this.registry.current.serverUrl || "http://localhost:1974").trim();
    return raw.replace(/\/+$/, "");
  }

  private getHeaders(): Record<string, string> {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      Accept: "application/json",
      "X-SailZen-Client": "vscode",
    };
    const token = this.registry.current.apiToken?.trim();
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
    return headers;
  }

  private async request<T>(
    method: string,
    apiPath: string,
    body?: unknown
  ): Promise<T> {
    const url = `${this.getBaseUrl()}/api/v1${apiPath}`;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);

    try {
      const resp = await fetch(url, {
        method,
        headers: this.getHeaders(),
        body: body !== undefined ? JSON.stringify(body) : undefined,
        signal: controller.signal,
      });

      if (!resp.ok) {
        const text = await resp.text().catch(() => "");
        throw new Error(`HTTP ${resp.status} ${method} ${apiPath}: ${text.slice(0, 200)}`);
      }
      return (await resp.json()) as T;
    } catch (err) {
      if (
        err instanceof Error &&
        (err.name === "AbortError" || err.message.includes("fetch failed"))
      ) {
        throw new ServerOfflineError(`Cannot reach sail_server at ${this.getBaseUrl()}`);
      }
      throw err;
    } finally {
      clearTimeout(timer);
    }
  }

  async healthCheck(): Promise<boolean> {
    try {
      const res = await this.request<{ status: string }>("GET", "/health");
      return res.status === "ok";
    } catch {
      return false;
    }
  }

  // --------------------------------------------------------------------------
  // Workbench & Rhythm v2
  // --------------------------------------------------------------------------

  async bootstrap(isoDate?: string): Promise<WorkbenchBootstrapDTO> {
    const qs = isoDate ? `?date=${encodeURIComponent(isoDate)}` : "";
    try {
      return await this.request<WorkbenchBootstrapDTO>("GET", `/workbench/bootstrap${qs}`);
    } catch (err) {
      // Graceful fallback for servers that haven't deployed /api/v1/workbench/bootstrap yet
      if (err instanceof Error && err.message.startsWith("HTTP 404 ")) {
        const [dash, topics, tickets] = await Promise.all([
          this.request<{
            date: string;
            timeline: WorkbenchBootstrapDTO["timeline"];
            projects: WorkbenchBootstrapDTO["projects"][number]["progress"][];
            focus_affairs: WorkbenchBootstrapDTO["focus_affairs"];
            overdue_affairs: WorkbenchBootstrapDTO["overdue_affairs"];
            degraded?: string[];
          }>("GET", `/rhythm/dashboard${qs}`),
          this.request<WorkbenchBootstrapDTO["topics"]>("GET", "/text/topic").catch(() => []),
          this.request<WorkbenchBootstrapDTO["pending_tickets"]>(
            "GET",
            "/tick/tickets?status=pending&limit=20"
          ).catch(() => []),
        ]);
        return {
          date: dash.date,
          timeline: dash.timeline,
          projects: (dash.projects || []).map((p) => {
            const slug =
              p.title
                .toLowerCase()
                .replace(/[^a-z0-9]+/g, "-")
                .replace(/^-+|-+$/g, "") || `venture-${p.affair_id}`;
            const linkedTopic = topics.find((t) => t.rhythm_venture_id === p.affair_id);
            return {
              progress: p,
              workbench: {
                slug,
                archetype: "general",
                vault_namespace: "",
                repo_hints: [],
                topic_id: linkedTopic?.id ?? null,
                original_work_id: null,
              },
            };
          }),
          focus_affairs: dash.focus_affairs || [],
          overdue_affairs: dash.overdue_affairs || [],
          topics,
          pending_tickets: tickets,
          degraded: [...(dash.degraded || []), "workbench_bootstrap_fallback"],
        };
      }
      throw err;
    }
  }

  async setBlockStatus(blockId: number, status: BlockStatus): Promise<TimeBlockDTO> {
    return this.request<TimeBlockDTO>("POST", `/rhythm/timeline/block/${blockId}/status`, {
      status,
    });
  }

  async createQuickTask(
    title: string,
    opts?: { description?: string; domain?: string; sourceFsPath?: string }
  ): Promise<AffairDTO> {
    this.privacyGuard.assertCloudUploadAllowed("createQuickTask", opts?.sourceFsPath);
    return this.request<AffairDTO>("POST", "/rhythm/affair/", {
      title,
      description: opts?.description || "",
      domain: opts?.domain || "work",
      kind: "task_oneoff",
    });
  }

  async completeMilestone(milestoneId: number): Promise<AffairDTO> {
    return this.request<AffairDTO>("POST", `/rhythm/venture/milestone/${milestoneId}/done`, {});
  }

  async updateProjectMeta(
    ventureId: number,
    patch: Partial<WorkbenchProjectMetaDTO>
  ): Promise<WorkbenchProjectItemDTO> {
    this.privacyGuard.assertCloudUploadAllowed("updateProjectMeta");
    return this.request<WorkbenchProjectItemDTO>(
      "PUT",
      `/workbench/project/${ventureId}`,
      patch
    );
  }

  async getContextPack(ventureId: number): Promise<WorkbenchContextPackDTO> {
    return this.request<WorkbenchContextPackDTO>(
      "GET",
      `/workbench/context-pack/${ventureId}`
    );
  }

  async sendQuickChat(
    text: string,
    opts?: {
      sourceFsPath?: string;
      domain?: "health" | "rhythm" | "finance" | "general";
      contextHints?: Record<string, unknown>;
    }
  ): Promise<QuickChatResponseDTO> {
    this.privacyGuard.assertCloudUploadAllowed("quickChat", opts?.sourceFsPath);
    return this.request<QuickChatResponseDTO>("POST", "/tick/quick-chat", {
      text,
      channel: "vscode_workbench",
      domain: opts?.domain || "rhythm",
      surface: "vscode_workbench",
      context_hints: opts?.contextHints || {},
    });
  }

  async getQuickChatHistory(
    domain: "health" | "rhythm" | "finance" | "general" = "rhythm",
    limit = 12
  ): Promise<Array<{ role: string; content: string; created_at?: string }>> {
    this.privacyGuard.assertCloudUploadAllowed("getQuickChatHistory");
    const res = await this.request<{ items?: Array<{ role: string; content: string; created_at?: string }> }>(
      "GET",
      `/tick/quick-chat/history?domain=${encodeURIComponent(domain)}&limit=${limit}`
    );
    return Array.isArray(res?.items) ? res.items : [];
  }

  async replyTicket(ticketId: number, reply: string): Promise<unknown> {
    this.privacyGuard.assertCloudUploadAllowed("replyTicket");
    return this.request<unknown>("POST", `/tick/tickets/${ticketId}/reply`, { reply });
  }

  async snoozeTicket(ticketId: number, hours = 1): Promise<unknown> {
    this.privacyGuard.assertCloudUploadAllowed("snoozeTicket");
    return this.request<unknown>("POST", `/tick/tickets/${ticketId}/snooze`, { hours });
  }

  // --------------------------------------------------------------------------
  // Content 2.0 (Works, TOC, Chapters, Topics, NoteItems, Clips, Vault Sync)
  // --------------------------------------------------------------------------

  async listWorks(params?: {
    pillar?: string;
    reading_status?: string;
    topic_id?: number;
    limit?: number;
  }): Promise<WorkDTO[]> {
    const search = new URLSearchParams();
    if (params?.pillar) search.set("pillar", params.pillar);
    if (params?.reading_status) search.set("reading_status", params.reading_status);
    if (params?.topic_id !== undefined) search.set("topic_id", String(params.topic_id));
    search.set("limit", String(params?.limit ?? 50));
    const qs = search.toString();
    return this.request<WorkDTO[]>("GET", `/text/work${qs ? `?${qs}` : ""}`);
  }

  async getEditionsByWork(workId: number): Promise<EditionDTO[]> {
    return this.request<EditionDTO[]>("GET", `/text/edition/work/${workId}`);
  }

  async getEditionToc(editionId: number): Promise<EditionTocDTO> {
    return this.request<EditionTocDTO>("GET", `/text/edition/${editionId}/toc`);
  }

  async getDocumentNode(nodeId: number): Promise<DocumentNodeDTO> {
    return this.request<DocumentNodeDTO>("GET", `/text/node/${nodeId}?include_content=true`);
  }

  async getTopicDetail(topicId: number): Promise<ContentTopicDetailDTO> {
    return this.request<ContentTopicDetailDTO>("GET", `/text/topic/${topicId}/detail`);
  }

  async pushTopicRhythmTask(
    topicId: number,
    req: { title: string; description?: string; work_id?: number; est_minutes?: number }
  ): Promise<TopicRhythmTaskSummaryDTO> {
    this.privacyGuard.assertCloudUploadAllowed("pushTopicRhythmTask");
    return this.request<TopicRhythmTaskSummaryDTO>(
      "POST",
      `/text/topic/${topicId}/push-rhythm-task`,
      req
    );
  }

  async listNoteItems(params?: {
    work_id?: number;
    category?: string;
    limit?: number;
  }): Promise<NoteItemListDTO> {
    const search = new URLSearchParams();
    if (params?.work_id !== undefined) search.set("work_id", String(params.work_id));
    if (params?.category) search.set("category", params.category);
    search.set("limit", String(params?.limit ?? 100));
    return this.request<NoteItemListDTO>("GET", `/text/note?${search.toString()}`);
  }

  async getNoteItemContent(noteId: number): Promise<NoteItemContentDTO> {
    return this.request<NoteItemContentDTO>("GET", `/text/note/${noteId}/content`);
  }

  async exportWorkClips(workId: number): Promise<WorkClipsExportDTO> {
    return this.request<WorkClipsExportDTO>("GET", `/text/work/${workId}/export-clips`);
  }

  async syncVaultNoteIndex(
    items: VaultNoteIndexItemDTO[],
    sourceVault = "local",
    vaultRootPath?: string
  ): Promise<VaultNoteIndexSyncResponseDTO> {
    this.privacyGuard.assertCloudUploadAllowed("syncVaultNoteIndex", vaultRootPath);
    return this.request<VaultNoteIndexSyncResponseDTO>("POST", "/text/vault/index/sync", {
      items,
      source_vault: sourceVault,
    });
  }

  async syncEditionChapter(
    editionId: number,
    req: ChapterSyncRequestDTO,
    sourceFsPath?: string
  ): Promise<ChapterSyncResponseDTO> {
    this.privacyGuard.assertCloudUploadAllowed("syncEditionChapter", sourceFsPath);
    return this.request<ChapterSyncResponseDTO>(
      "PUT",
      `/text/edition/${editionId}/chapter-sync`,
      req
    );
  }

  // --------------------------------------------------------------------------
  // VS Code Extension OTA Release (/api/v1/workbench/release/*)
  // --------------------------------------------------------------------------

  async getLatestWorkbenchRelease(): Promise<WorkbenchReleaseInfoDTO> {
    return this.request<WorkbenchReleaseInfoDTO>("GET", "/workbench/release/latest");
  }

  /** Download raw binary (e.g. .vsix) from server path (relative to host or /api/v1). */
  async downloadBinary(pathOrUrl: string): Promise<Buffer> {
    const url = pathOrUrl.startsWith("http")
      ? pathOrUrl
      : pathOrUrl.startsWith("/")
      ? `${this.getBaseUrl()}${pathOrUrl}`
      : `${this.getBaseUrl()}/api/v1/${pathOrUrl}`;

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), Math.max(this.timeoutMs, 60000));
    try {
      const headers: Record<string, string> = {
        "X-SailZen-Client": "vscode",
      };
      const token = this.registry.current.apiToken?.trim();
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }
      const resp = await fetch(url, { method: "GET", headers, signal: controller.signal });
      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status} GET ${pathOrUrl}`);
      }
      const arr = await resp.arrayBuffer();
      return Buffer.from(arr);
    } finally {
      clearTimeout(timer);
    }
  }
}
