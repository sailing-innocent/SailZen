import { MachineRegistry } from "../machine/machineConfig";
import { PrivacyGuard } from "../machine/privacyGuard";
import {
  AffairDTO,
  BlockStatus,
  QuickChatResponseDTO,
  TimeBlockDTO,
  WorkbenchBootstrapDTO,
  WorkbenchContextPackDTO,
  WorkbenchProjectItemDTO,
  WorkbenchProjectMetaDTO,
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
    private readonly timeoutMs = 8000
  ) {}

  private getBaseUrl(): string {
    const raw = (this.registry.current.serverUrl || "http://localhost:1974").trim();
    return raw.replace(/\/+$/, "");
  }

  private getHeaders(): Record<string, string> {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      Accept: "application/json",
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
      if (err instanceof Error && (err.name === "AbortError" || err.message.includes("fetch failed"))) {
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

  /** Single-RTT bootstrap for Today & Rhythm + Projects & Content + Pending Tickets. */
  async bootstrap(isoDate?: string): Promise<WorkbenchBootstrapDTO> {
    const qs = isoDate ? `?date=${encodeURIComponent(isoDate)}` : "";
    return this.request<WorkbenchBootstrapDTO>("GET", `/workbench/bootstrap${qs}`);
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

  async sendQuickChat(message: string, sourceFsPath?: string): Promise<QuickChatResponseDTO> {
    this.privacyGuard.assertCloudUploadAllowed("quickChat", sourceFsPath);
    return this.request<QuickChatResponseDTO>("POST", "/tick/quick-chat", {
      message,
      channel: "vscode_workbench",
    });
  }
}
