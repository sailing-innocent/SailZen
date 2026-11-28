import * as vscode from "vscode";
import { PrivacyViolationError } from "../../core/machine/privacyGuard";
import { WorkbenchState } from "../../core/workbenchState";

function getNonce(): string {
  const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
  let out = "";
  for (let i = 0; i < 24; i++) {
    out += chars[Math.floor(Math.random() * chars.length)];
  }
  return out;
}

interface ChatEntry {
  role: "user" | "agent" | "system";
  text: string;
}

const QUICK_ACTIONS = [
  { label: "重排今天", prompt: "帮我结合当前剩余时间重排今天的时间线" },
  { label: "记录阻塞", prompt: "当前任务遇到阻塞，帮我记一下并调整后续排期" },
  { label: "记一条待办", prompt: "帮我记一条待办：" },
  { label: "查项目倒排", prompt: "/projects" },
];

export class QuickChatWebviewProvider implements vscode.WebviewViewProvider {
  public static readonly viewId = "sailzen.quickChatView";
  private view: vscode.WebviewView | null = null;
  private history: ChatEntry[] = [];
  private historyLoaded = false;

  constructor(private readonly state: WorkbenchState) {
    this.state.onDidContextChange(() => this.syncState());
  }

  private async ensureHistoryLoaded(): Promise<void> {
    if (this.historyLoaded || this.state.privacyGuard.isWorkOfflineActive()) return;
    this.historyLoaded = true;
    try {
      const items = await this.state.apiClient.getQuickChatHistory("rhythm", 12);
      if (items.length > 0 && this.history.length === 0) {
        this.history = items.map((it) => ({
          role: it.role === "user" ? "user" : "agent",
          text: it.content,
        }));
      }
    } catch {
      // Non-fatal: server might be offline or older version
    }
  }

  resolveWebviewView(webviewView: vscode.WebviewView): void {
    this.view = webviewView;
    webviewView.webview.options = { enableScripts: true };
    webviewView.webview.html = this.renderHtml();

    webviewView.webview.onDidReceiveMessage(async (msg) => {
      if (!msg || typeof msg !== "object") return;
      if (msg.type === "ready") {
        await this.ensureHistoryLoaded();
        this.syncState();
        return;
      }
      if (msg.type === "send" && typeof msg.text === "string" && msg.text.trim()) {
        const text = msg.text.trim();
        this.history.push({ role: "user", text });
        this.syncState(true);

        try {
          const contextHints: Record<string, unknown> = {};
          if (this.state.activeProject) {
            contextHints.active_project = this.state.activeProject.workbench.slug;
            contextHints.active_project_title = this.state.activeProject.progress.title;
          }
          const resp = await this.state.apiClient.sendQuickChat(text, {
            domain: "rhythm",
            contextHints,
          });
          const replyText =
            (typeof resp.reply === "string" && resp.reply) ||
            (typeof resp.message === "string" && resp.message) ||
            JSON.stringify(resp);
          this.history.push({ role: "agent", text: replyText });
          // Auto-refresh Rhythm & Projects after SailTick adjusts schedule
          void this.state.refreshServerData();
        } catch (err) {
          const msgText =
            err instanceof PrivacyViolationError
              ? err.message
              : err instanceof Error
              ? err.message
              : String(err);
          this.history.push({ role: "system", text: msgText });
        }
        this.syncState(false);
      }
    });

    void this.ensureHistoryLoaded().then(() => this.syncState());
  }

  private syncState(busy = false): void {
    if (!this.view) return;
    void this.view.webview.postMessage({
      type: "state",
      offline: this.state.privacyGuard.isWorkOfflineActive(),
      busy,
      history: this.history.slice(-20),
    });
  }

  private renderHtml(): string {
    const nonce = getNonce();
    const quickButtonsHtml = QUICK_ACTIONS.map(
      (qa, idx) =>
        `<button class="chip" data-idx="${idx}" data-prompt="${qa.prompt.replace(/"/g, "&quot;")}">${qa.label}</button>`
    ).join("");
    return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'nonce-${nonce}';" />
<style>
  body { font-family: var(--vscode-font-family); font-size: 12px; color: var(--vscode-foreground); margin: 0; padding: 6px 8px; display: flex; flex-direction: column; height: 100vh; box-sizing: border-box; }
  .banner { background: var(--vscode-inputValidation-warningBackground); border: 1px solid var(--vscode-inputValidation-warningBorder); padding: 4px 6px; border-radius: 3px; margin-bottom: 6px; font-size: 11px; display: none; }
  .messages { flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 6px; margin-bottom: 6px; }
  .msg { padding: 5px 7px; border-radius: 4px; white-space: pre-wrap; word-break: break-word; line-height: 1.4; }
  .msg.user { background: var(--vscode-button-secondaryBackground); align-self: flex-end; max-width: 90%; }
  .msg.agent { background: var(--vscode-editor-inactiveSelectionBackground); align-self: flex-start; max-width: 95%; }
  .msg.system { color: var(--vscode-errorForeground); font-size: 11px; }
  .hint { opacity: 0.65; font-size: 11px; }
  .chips { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 5px; }
  .chip { background: var(--vscode-badge-background); color: var(--vscode-badge-foreground); border: none; border-radius: 10px; padding: 2px 7px; font-size: 10.5px; cursor: pointer; }
  .chip:hover { opacity: 0.85; }
  .input-row { display: flex; gap: 4px; }
  input { flex: 1; background: var(--vscode-input-background); color: var(--vscode-input-foreground); border: 1px solid var(--vscode-input-border); border-radius: 3px; padding: 4px 6px; font-size: 12px; }
  button.send { background: var(--vscode-button-background); color: var(--vscode-button-foreground); border: none; border-radius: 3px; padding: 4px 8px; cursor: pointer; font-size: 12px; }
  button:disabled { opacity: 0.5; cursor: default; }
</style>
</head>
<body>
  <div class="banner" id="offlineBanner">🔒 Work Vault 离线模式：已拦截 SailTick 云端对话。</div>
  <div class="messages" id="messages">
    <div class="hint">节奏规划师（与手机规划页/Web Rhythm 共享会话，支持 /today、/projects）。</div>
  </div>
  <div class="chips" id="chips">${quickButtonsHtml}</div>
  <div class="input-row">
    <input id="chatInput" type="text" placeholder="如：下午加了个1h评审，重排一下..." />
    <button class="send" id="sendBtn">Send</button>
  </div>
  <script nonce="${nonce}">
    const vscode = acquireVsCodeApi();
    const messagesEl = document.getElementById("messages");
    const inputEl = document.getElementById("chatInput");
    const sendBtn = document.getElementById("sendBtn");
    const banner = document.getElementById("offlineBanner");
    const chipsEl = document.getElementById("chips");

    function send(explicit) {
      const val = (explicit !== undefined ? explicit : inputEl.value).trim();
      if (!val || sendBtn.disabled) return;
      if (explicit === undefined) inputEl.value = "";
      vscode.postMessage({ type: "send", text: val });
    }

    sendBtn.addEventListener("click", () => send());
    inputEl.addEventListener("keydown", (e) => {
      if (e.key === "Enter") send();
    });
    chipsEl.addEventListener("click", (e) => {
      const btn = e.target.closest("button.chip");
      if (!btn || sendBtn.disabled) return;
      const p = btn.getAttribute("data-prompt") || "";
      if (p.endsWith("：")) {
        inputEl.value = p;
        inputEl.focus();
      } else {
        send(p);
      }
    });

    window.addEventListener("message", (event) => {
      const msg = event.data;
      if (msg.type !== "state") return;
      banner.style.display = msg.offline ? "block" : "none";
      inputEl.disabled = msg.offline || msg.busy;
      sendBtn.disabled = msg.offline || msg.busy;
      sendBtn.textContent = msg.busy ? "..." : "Send";

      messagesEl.innerHTML = "";
      if (!msg.history || msg.history.length === 0) {
        const h = document.createElement("div");
        h.className = "hint";
        h.textContent = "节奏规划师（与手机规划页/Web Rhythm 共享会话，支持 /today、/projects）。";
        messagesEl.appendChild(h);
      } else {
        for (const item of msg.history) {
          const div = document.createElement("div");
          div.className = "msg " + item.role;
          div.textContent = item.text;
          messagesEl.appendChild(div);
        }
        messagesEl.scrollTop = messagesEl.scrollHeight;
      }
    });

    vscode.postMessage({ type: "ready" });
  </script>
</body>
</html>`;
  }
}
