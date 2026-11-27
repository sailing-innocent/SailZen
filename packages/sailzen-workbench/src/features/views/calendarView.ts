import * as vscode from "vscode";
import { WorkbenchState } from "../../core/workbenchState";

function getNonce(): string {
  const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
  let out = "";
  for (let i = 0; i < 24; i++) {
    out += chars[Math.floor(Math.random() * chars.length)];
  }
  return out;
}

export class CalendarWebviewProvider implements vscode.WebviewViewProvider {
  public static readonly viewId = "sailzen.calendarView";
  private view: vscode.WebviewView | null = null;
  private currentYear: number;
  private currentMonth: number; // 1..12

  constructor(private readonly state: WorkbenchState) {
    const now = new Date();
    this.currentYear = now.getFullYear();
    this.currentMonth = now.getMonth() + 1;
    this.state.onDidVaultChange(() => this.postMonthState());
  }

  resolveWebviewView(webviewView: vscode.WebviewView): void {
    this.view = webviewView;
    webviewView.webview.options = { enableScripts: true };
    webviewView.webview.html = this.renderHtml(webviewView.webview);

    webviewView.webview.onDidReceiveMessage(async (msg) => {
      if (!msg || typeof msg !== "object") return;
      if (msg.type === "ready") {
        this.postMonthState();
      } else if (msg.type === "prevMonth") {
        this.shiftMonth(-1);
      } else if (msg.type === "nextMonth") {
        this.shiftMonth(1);
      } else if (msg.type === "today") {
        const now = new Date();
        this.currentYear = now.getFullYear();
        this.currentMonth = now.getMonth() + 1;
        this.postMonthState();
        await this.state.openDailyJournal(now);
      } else if (msg.type === "openDay" && typeof msg.day === "number") {
        const target = new Date(this.currentYear, this.currentMonth - 1, msg.day);
        await this.state.openDailyJournal(target);
      }
    });

    this.postMonthState();
  }

  private shiftMonth(delta: number): void {
    const d = new Date(this.currentYear, this.currentMonth - 1 + delta, 1);
    this.currentYear = d.getFullYear();
    this.currentMonth = d.getMonth() + 1;
    this.postMonthState();
  }

  private postMonthState(): void {
    if (!this.view) return;
    const daysMap = this.state.vaultIndex?.getDailyJournalDays(
      this.currentYear,
      this.currentMonth
    );
    const existingDays = daysMap ? Array.from(daysMap.keys()) : [];
    const now = new Date();
    void this.view.webview.postMessage({
      type: "monthData",
      year: this.currentYear,
      month: this.currentMonth,
      existingDays,
      today: {
        year: now.getFullYear(),
        month: now.getMonth() + 1,
        day: now.getDate(),
      },
    });
  }

  private renderHtml(webview: vscode.Webview): string {
    const nonce = getNonce();
    return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'nonce-${nonce}';" />
<style>
  body { font-family: var(--vscode-font-family); font-size: 12px; color: var(--vscode-foreground); padding: 6px 8px; margin: 0; }
  .header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px; }
  .title { font-weight: 600; }
  .nav { display: flex; gap: 4px; }
  button { background: var(--vscode-button-secondaryBackground); color: var(--vscode-button-secondaryForeground); border: none; border-radius: 3px; padding: 2px 6px; cursor: pointer; font-size: 11px; }
  button:hover { background: var(--vscode-button-secondaryHoverBackground); }
  .grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 2px; text-align: center; }
  .dow { opacity: 0.65; font-size: 10px; padding-bottom: 3px; }
  .cell { padding: 4px 0; border-radius: 4px; cursor: pointer; position: relative; }
  .cell:hover { background: var(--vscode-list-hoverBackground); }
  .cell.empty { cursor: default; pointer-events: none; }
  .cell.today { outline: 1px solid var(--vscode-focusBorder); font-weight: 700; }
  .cell.has-note::after { content: ""; display: block; width: 4px; height: 4px; border-radius: 50%; background: var(--vscode-charts-blue, #3794ff); margin: 1px auto 0; }
</style>
</head>
<body>
  <div class="header">
    <span class="title" id="monthLabel">...</span>
    <div class="nav">
      <button id="prevBtn">&lt;</button>
      <button id="todayBtn">Today</button>
      <button id="nextBtn">&gt;</button>
    </div>
  </div>
  <div class="grid" id="dowRow">
    <div class="dow">Mo</div><div class="dow">Tu</div><div class="dow">We</div>
    <div class="dow">Th</div><div class="dow">Fr</div><div class="dow">Sa</div><div class="dow">Su</div>
  </div>
  <div class="grid" id="daysGrid"></div>
  <script nonce="${nonce}">
    const vscode = acquireVsCodeApi();
    const label = document.getElementById("monthLabel");
    const grid = document.getElementById("daysGrid");

    document.getElementById("prevBtn").addEventListener("click", () => vscode.postMessage({ type: "prevMonth" }));
    document.getElementById("nextBtn").addEventListener("click", () => vscode.postMessage({ type: "nextMonth" }));
    document.getElementById("todayBtn").addEventListener("click", () => vscode.postMessage({ type: "today" }));

    window.addEventListener("message", (event) => {
      const msg = event.data;
      if (msg.type !== "monthData") return;
      const { year, month, existingDays, today } = msg;
      const existing = new Set(existingDays || []);
      label.textContent = year + "-" + String(month).padStart(2, "0");

      const firstDow = (new Date(year, month - 1, 1).getDay() + 6) % 7; // Mon=0..Sun=6
      const daysInMonth = new Date(year, month, 0).getDate();
      grid.innerHTML = "";

      for (let i = 0; i < firstDow; i++) {
        const empty = document.createElement("div");
        empty.className = "cell empty";
        grid.appendChild(empty);
      }

      for (let d = 1; d <= daysInMonth; d++) {
        const cell = document.createElement("div");
        cell.className = "cell";
        cell.textContent = String(d);
        if (existing.has(d)) cell.classList.add("has-note");
        if (today && today.year === year && today.month === month && today.day === d) {
          cell.classList.add("today");
        }
        cell.addEventListener("click", () => vscode.postMessage({ type: "openDay", day: d }));
        grid.appendChild(cell);
      }
    });

    vscode.postMessage({ type: "ready" });
  </script>
</body>
</html>`;
  }
}
