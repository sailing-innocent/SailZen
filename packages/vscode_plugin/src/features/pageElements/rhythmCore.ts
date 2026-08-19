/**
 * @file rhythmCore.ts
 * @brief sail_server-backed Rhythm / Affair page element core (vscode-free).
 *
 * This module is deliberately free of any `vscode` / `Logger` imports so it
 * can run in every process that performs note rendering:
 *
 * - the VSCode extension host (dev mode engine, via `rhythmPageElement.ts`);
 * - the standalone engine child process (prod mode, via `server.ts`);
 * - plain jest unit tests.
 *
 * Rhythm data comes from the remote sail_server
 * (`GET /api/v1/rhythm/timeline/day-dashboard?date=YYYY-MM-DD`), which
 * aggregates the day timeline, energy budget, checkins and priority affairs.
 *
 * The providers are date-aware: for a daily journal note
 * (`journal.daily.YYYY.MM.DD`) they render the rhythm dashboard of *that* date.
 * The registry-level cache key already contains `note.id`, and the module-level
 * cache here is keyed by `${baseUrl}|${date}`, so different dates never pollute
 * each other.
 */
import type {
  NotePageElementProvider,
  PageElementRegistry,
  PageElementRenderContext,
} from "@saili/unified";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type RhythmAffair = {
  id: number;
  title: string;
  description?: string;
  domain?: "life" | "work" | "career";
  kind?: string;
  state?: string;
  importance?: number;
  urgency_ddl?: string;
  energy_cost?: number;
  est_minutes?: number;
  window_start?: string;
  window_end?: string;
  score?: number;
};

export type RhythmBlock = {
  id: number;
  affair_id?: number;
  affair_title?: string;
  affair_kind?: string;
  block_type: string;
  start_time: string;
  end_time: string;
  status: string;
  energy_cost?: number;
};

export type DomainMinutes = { life: number; work: number; career: number };

export type CheckinItem = {
  affair: RhythmAffair;
  done_today: boolean;
  last_result?: string;
  week_done_count?: number;
  week_target?: number;
};

export type PriorityAffair = {
  affair: RhythmAffair;
  reason: string;
  suggested_slot?: string;
};

export type RhythmDashboard = {
  date: string;
  day_id: number;
  plan_version: number;
  blocks: RhythmBlock[];
  domain_minutes: DomainMinutes;
  energy_budget: number;
  energy_consumed: number;
  energy_available: number;
  buffer_total_minutes: number;
  buffer_free_minutes: number;
  checkins?: {
    date: string;
    precepts: CheckinItem[];
    habits: CheckinItem[];
  };
  priorities: PriorityAffair[];
  insights: string[];
  warnings: string[];
  error?: string;
};

export type RhythmLogFn = (
  level: "debug" | "info" | "warn" | "error",
  msg: string
) => void;

export type RhythmCoreDeps = {
  /** 解析 sail_server 地址，例如 http://localhost:1974（每次查询时调用）。 */
  resolveBaseUrl: () => string;
  /** provider/registry 缓存 TTL（毫秒），默认 5min。创建 provider 时读取。 */
  resolveCacheTtlMs?: () => number;
  /** 测试注入的 fetch 实现；默认全局 fetch。 */
  fetchImpl?: typeof fetch;
  /** 可选日志回调，由 vscode 胶水层注入 Logger。 */
  log?: RhythmLogFn;
  /**
   * 非 journal 笔记的 RHYTHM_PREFIX 帮助内容渲染器。由胶水层注入
   * （基于 unified 的 renderPageElementHelp）；缺省时使用内置简版帮助。
   */
  renderPrefixHelp?: (ctx: PageElementRenderContext) => string;
};

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Default client-side cache TTL for rhythm dashboard queries (5 minutes). */
export const DEFAULT_RHYTHM_CACHE_TTL_MS = 5 * 60 * 1000;

/** Default timeout for a single sail_server rhythm request. */
export const DEFAULT_RHYTHM_FETCH_TIMEOUT_MS = 8_000;

const DAILY_JOURNAL_FNAME_REGEX = /(^|\.)daily\.(\d{4})\.(\d{2})\.(\d{2})$/;

const DATE_ARG_REGEX = /^\d{4}-\d{2}-\d{2}$/;

const WEEKDAYS_CN = ["日", "一", "二", "三", "四", "五", "六"];

const BLOCK_TYPE_LABELS: Record<string, string> = {
  sleep: "睡眠",
  commute: "通勤",
  work_window: "工作窗",
  micro_rest: "微休息",
  meal: "用餐",
  precept: "戒律",
  habit: "习惯",
  fixed: "固定",
  focus: "专注",
  light: "轻量",
  career: "事业",
  rest: "休息",
  buffer: "缓冲",
  async_kickoff: "异步启动",
  async_review: "异步审阅",
  async_wait: "异步等待",
};

const BLOCK_TYPE_EMOJI: Record<string, string> = {
  sleep: "🌙",
  commute: "🚗",
  work_window: "💼",
  micro_rest: "☕",
  meal: "🍽",
  precept: "📜",
  habit: "🔄",
  fixed: "📌",
  focus: "🎯",
  light: "💡",
  career: "🚀",
  rest: "🛋",
  buffer: "🧽",
  async_kickoff: "🚀",
  async_review: "👀",
  async_wait: "⏳",
};

const STATUS_LABELS: Record<string, string> = {
  PLANNED: "已计划",
  DOING: "进行中",
  DONE: "已完成",
  SKIPPED: "已跳过",
  MOVED: "已移动",
};

const STATE_LABELS: Record<string, string> = {
  INBOX: "收件箱",
  PLANNED: "已计划",
  SCHEDULED: "已排程",
  DOING: "进行中",
  DONE: "已完成",
  DEFERRED: "已推迟",
  CANCELED: "已取消",
  ACTIVE: "活跃",
  PAUSED: "已暂停",
  ARCHIVED: "已归档",
  KICKOFF: "启动",
  DELEGATED: "已委托",
  REVIEWING: "审阅中",
  COMPLETED: "已完成",
};

const DOMAIN_LABELS: Record<string, string> = {
  life: "生活",
  work: "工作",
  career: "事业",
};

const DOMAIN_COLORS: Record<string, string> = {
  life: "#22c55e",
  work: "#3b82f6",
  career: "#a855f7",
};

const RESULT_EMOJI: Record<string, string> = {
  kept: "✅",
  violated: "❌",
  done: "✅",
  missed: "❌",
  exempt: "🆓",
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

export function parseDailyJournalDate(
  fname: string
): { year: number; month: number; day: number } | undefined {
  const m = DAILY_JOURNAL_FNAME_REGEX.exec(fname);
  if (!m) return undefined;
  return {
    year: Number(m[2]),
    month: Number(m[3]),
    day: Number(m[4]),
  };
}

const pad2 = (n: number) => String(n).padStart(2, "0");

export function todayDateStr(now: Date = new Date()): string {
  return `${now.getFullYear()}-${pad2(now.getMonth() + 1)}-${pad2(now.getDate())}`;
}

export function formatDateLabel(dateStr: string): string {
  const m = DATE_ARG_REGEX.exec(dateStr);
  if (!m) return dateStr;
  const [y, mo, d] = dateStr.split("-").map((s) => Number(s));
  const weekday = WEEKDAYS_CN[new Date(y, mo - 1, d).getDay()];
  return `${dateStr} 周${weekday}`;
}

function journalDateStr(fname: string): string | undefined {
  const d = parseDailyJournalDate(fname);
  if (!d) return undefined;
  return `${d.year}-${pad2(d.month)}-${pad2(d.day)}`;
}

function timeLabel(iso?: string): string | undefined {
  if (!iso) return undefined;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return undefined;
  return `${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
}

function formatDuration(minutes: number): string {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  if (h === 0) return `${m}m`;
  if (m === 0) return `${h}h`;
  return `${h}h${m}m`;
}

function numOrZero(v: unknown): number {
  return typeof v === "number" && Number.isFinite(v) ? v : 0;
}

function strOrUndef(v: unknown): string | undefined {
  return typeof v === "string" && v ? v : undefined;
}

function objOrEmpty(v: unknown): Record<string, unknown> {
  return v && typeof v === "object" && !Array.isArray(v) ? (v as Record<string, unknown>) : {};
}

function arrOrEmpty(v: unknown): unknown[] {
  return Array.isArray(v) ? v : [];
}

function normalizeAffair(raw: any): RhythmAffair {
  return {
    id: Number(raw?.id ?? 0),
    title: String(raw?.title ?? ""),
    description: strOrUndef(raw?.description),
    domain: ["life", "work", "career"].includes(raw?.domain)
      ? raw.domain
      : undefined,
    kind: strOrUndef(raw?.kind),
    state: strOrUndef(raw?.state),
    importance: numOrZero(raw?.importance),
    urgency_ddl: strOrUndef(raw?.urgency_ddl),
    energy_cost: numOrZero(raw?.energy_cost),
    est_minutes: numOrZero(raw?.est_minutes),
    window_start: strOrUndef(raw?.window_start),
    window_end: strOrUndef(raw?.window_end),
    score: numOrZero(raw?.score),
  };
}

function normalizeBlock(raw: any): RhythmBlock {
  return {
    id: Number(raw?.id ?? 0),
    affair_id: raw?.affair_id == null ? undefined : Number(raw.affair_id),
    affair_title: strOrUndef(raw?.affair_title),
    affair_kind: strOrUndef(raw?.affair_kind),
    block_type: String(raw?.block_type ?? ""),
    start_time: String(raw?.start_time ?? ""),
    end_time: String(raw?.end_time ?? ""),
    status: String(raw?.status ?? "PLANNED"),
    energy_cost: numOrZero(raw?.energy_cost),
  };
}

function normalizeCheckin(raw: any): CheckinItem {
  return {
    affair: normalizeAffair(raw?.affair),
    done_today: Boolean(raw?.done_today),
    last_result: strOrUndef(raw?.last_result),
    week_done_count:
      typeof raw?.week_done_count === "number" ? raw.week_done_count : undefined,
    week_target:
      typeof raw?.week_target === "number" ? raw.week_target : undefined,
  };
}

function normalizePriority(raw: any): PriorityAffair {
  return {
    affair: normalizeAffair(raw?.affair),
    reason: String(raw?.reason ?? ""),
    suggested_slot: strOrUndef(raw?.suggested_slot),
  };
}

function normalizeDomainMinutes(raw: any): DomainMinutes {
  return {
    life: numOrZero(raw?.life),
    work: numOrZero(raw?.work),
    career: numOrZero(raw?.career),
  };
}

export function normalizeDayDashboard(
  json: any,
  fallbackDate?: string
): RhythmDashboard {
  const date =
    typeof json?.date === "string" && json.date
      ? json.date
      : fallbackDate ?? "";
  const blocks: RhythmBlock[] = arrOrEmpty(json?.blocks)
    .filter((b) => b && typeof b === "object")
    .map(normalizeBlock);
  const priorities: PriorityAffair[] = arrOrEmpty(json?.priorities)
    .filter((p) => p && typeof p === "object")
    .map(normalizePriority);
  const insights: string[] = arrOrEmpty(json?.insights).filter(
    (s): s is string => typeof s === "string"
  );
  const warnings: string[] = arrOrEmpty(json?.warnings).filter(
    (s): s is string => typeof s === "string"
  );

  let checkins: RhythmDashboard["checkins"] = undefined;
  const rawCheckins = objOrEmpty(json?.checkins);
  if (Object.keys(rawCheckins).length > 0) {
    checkins = {
      date:
        typeof rawCheckins.date === "string" && rawCheckins.date
          ? rawCheckins.date
          : date,
      precepts: arrOrEmpty(rawCheckins.precepts)
        .filter((c) => c && typeof c === "object")
        .map(normalizeCheckin),
      habits: arrOrEmpty(rawCheckins.habits)
        .filter((c) => c && typeof c === "object")
        .map(normalizeCheckin),
    };
  }

  return {
    date,
    day_id: Number(json?.day_id ?? 0),
    plan_version: Number(json?.plan_version ?? 0),
    blocks,
    domain_minutes: normalizeDomainMinutes(json?.domain_minutes),
    energy_budget: numOrZero(json?.energy_budget) || 100,
    energy_consumed: numOrZero(json?.energy_consumed),
    energy_available: numOrZero(json?.energy_available),
    buffer_total_minutes: numOrZero(json?.buffer_total_minutes),
    buffer_free_minutes: numOrZero(json?.buffer_free_minutes),
    checkins,
    priorities,
    insights,
    warnings,
  };
}

// ---------------------------------------------------------------------------
// sail_server rhythm client
// ---------------------------------------------------------------------------

export type SailServerRhythmClient = {
  getDayDashboard(dateStr: string): Promise<RhythmDashboard>;
};

function unavailableDashboard(dateStr: string, error?: string): RhythmDashboard {
  return {
    date: dateStr,
    day_id: 0,
    plan_version: 0,
    blocks: [],
    domain_minutes: { life: 0, work: 0, career: 0 },
    energy_budget: 100,
    energy_consumed: 0,
    energy_available: 100,
    buffer_total_minutes: 0,
    buffer_free_minutes: 0,
    priorities: [],
    insights: [],
    warnings: [],
    error,
  };
}

export function createSailServerRhythmClient(deps: {
  resolveBaseUrl: () => string;
  timeoutMs?: number;
  fetchImpl?: typeof fetch;
}): SailServerRhythmClient {
  const fetchImpl = deps.fetchImpl ?? fetch;
  const timeoutMs = deps.timeoutMs ?? DEFAULT_RHYTHM_FETCH_TIMEOUT_MS;
  return {
    async getDayDashboard(dateStr: string): Promise<RhythmDashboard> {
      const baseUrl = deps.resolveBaseUrl().replace(/\/+$/, "");
      const url = `${baseUrl}/api/v1/rhythm/timeline/day-dashboard?date=${encodeURIComponent(dateStr)}`;
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), timeoutMs);
      try {
        const resp = await fetchImpl(url, { signal: controller.signal });
        if (!resp.ok) {
          return unavailableDashboard(dateStr, `HTTP ${resp.status}`);
        }
        const json = await resp.json();
        return normalizeDayDashboard(json, dateStr);
      } catch (err: any) {
        const msg =
          err?.name === "AbortError" ? "请求超时" : err?.message ?? String(err);
        return unavailableDashboard(dateStr, msg);
      } finally {
        clearTimeout(timer);
      }
    },
  };
}

// ---------------------------------------------------------------------------
// Per-date rhythm cache
// ---------------------------------------------------------------------------

export type RhythmCache = {
  get(baseUrl: string, dateStr: string): RhythmDashboard | undefined;
  set(baseUrl: string, dateStr: string, data: RhythmDashboard): void;
  clear(): void;
};

export function createRhythmCache(opts: {
  resolveTtlMs: () => number;
  now?: () => number;
}): RhythmCache {
  const map = new Map<string, { data: RhythmDashboard; expiresAt: number }>();
  const now = opts.now ?? Date.now;
  const keyOf = (baseUrl: string, dateStr: string) => `${baseUrl}|${dateStr}`;
  return {
    get(baseUrl, dateStr) {
      const key = keyOf(baseUrl, dateStr);
      const entry = map.get(key);
      if (!entry) return undefined;
      if (entry.expiresAt <= now()) {
        map.delete(key);
        return undefined;
      }
      return entry.data;
    },
    set(baseUrl, dateStr, data) {
      if (data.error) return; // 失败不缓存，下次渲染重试
      const ttlMs = opts.resolveTtlMs();
      map.set(keyOf(baseUrl, dateStr), { data, expiresAt: now() + ttlMs });
    },
    clear() {
      map.clear();
    },
  };
}

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------

const CARD_STYLE = [
  "border: 1px solid var(--vscode-panel-border, #d0d7de)",
  "border-radius: 8px",
  "padding: 10px 14px",
  "margin: 8px 0",
  "background: var(--vscode-textBlockQuote-background, rgba(127,127,127,0.06))",
].join("; ");

const CARD_TITLE_STYLE = [
  "font-weight: 600",
  "margin-bottom: 8px",
  "color: var(--vscode-foreground, #24292f)",
].join("; ");

const SECTION_TITLE_STYLE = [
  "font-weight: 600",
  "margin: 10px 0 6px 0",
  "font-size: 0.95em",
  "color: var(--vscode-foreground, #24292f)",
].join("; ");

const MUTED_STYLE = "color: var(--vscode-descriptionForeground, #6a737d)";

const BADGE_STYLE = [
  "display: inline-block",
  "font-size: 0.75em",
  "border: 1px solid var(--vscode-panel-border, #d0d7de)",
  "border-radius: 4px",
  "padding: 0 5px",
  "margin-left: 6px",
  MUTED_STYLE,
].join("; ");

function badge(text: string, color?: string): string {
  const extra = color ? ` border-color: ${color}; color: ${color}` : "";
  return `<span style="${BADGE_STYLE}${extra}">${escapeHtml(text)}</span>`;
}

function statusBadge(status?: string): string {
  const label = STATUS_LABELS[status ?? ""] ?? status ?? "";
  return badge(label);
}

function stateBadge(state?: string): string {
  const label = STATE_LABELS[state ?? ""] ?? state ?? "";
  return badge(label);
}

function domainBadge(domain?: string): string {
  const label = DOMAIN_LABELS[domain ?? ""] ?? domain ?? "";
  const color = DOMAIN_COLORS[domain ?? ""];
  return badge(label, color);
}

function importanceStars(importance?: number): string {
  const n = Math.max(0, Math.min(5, importance ?? 0));
  return "★".repeat(n) + "☆".repeat(5 - n);
}

function renderEnergyBar(dashboard: RhythmDashboard): string {
  const budget = Math.max(1, dashboard.energy_budget);
  const consumed = dashboard.energy_consumed;
  const available = dashboard.energy_available;
  const pct = Math.min(100, Math.round((consumed / budget) * 100));
  const ratio = available / budget;
  let color = "#22c55e"; // green
  if (ratio <= 0.2) color = "#ef4444";
  else if (ratio <= 0.4) color = "#f97316";

  return [
    `<div class="sail-rhythm-energy">`,
    `<div style="display:flex;justify-content:space-between;margin-bottom:4px;">`,
    `<span>⚡ 精力预算</span>`,
    `<span>${consumed}/${budget}（余 ${available}）</span>`,
    `</div>`,
    `<div class="sail-rhythm-energy-bar" style="height:8px;background:var(--vscode-panel-border,#d0d7de);border-radius:4px;overflow:hidden;">`,
    `<div style="width:${pct}%;background:${color};height:100%;border-radius:4px;"></div>`,
    `</div>`,
    `</div>`,
  ].join("");
}

function renderDomainBars(domain_minutes: DomainMinutes): string {
  const total = domain_minutes.life + domain_minutes.work + domain_minutes.career;
  if (total === 0) return "";
  const rows = (["life", "work", "career"] as const).map((key) => {
    const minutes = domain_minutes[key];
    const pct = Math.round((minutes / total) * 100);
    return [
      `<div style="display:flex;align-items:center;gap:8px;margin:3px 0;">`,
      `<span style="width:40px;font-size:0.85em;">${DOMAIN_LABELS[key]}</span>`,
      `<div style="flex:1;height:8px;background:var(--vscode-panel-border,#d0d7de);border-radius:4px;overflow:hidden;">`,
      `<div style="width:${pct}%;background:${DOMAIN_COLORS[key]};height:100%;border-radius:4px;"></div>`,
      `</div>`,
      `<span style="width:60px;text-align:right;font-size:0.8em;${MUTED_STYLE}">${formatDuration(minutes)} (${pct}%)</span>`,
      `</div>`,
    ].join("");
  });
  return [
    `<div style="${SECTION_TITLE_STYLE}">三域投入</div>`,
    ...rows,
  ].join("");
}

function renderTimeline(dashboard: RhythmDashboard): string {
  const blocks = [...dashboard.blocks].sort((a, b) =>
    a.start_time.localeCompare(b.start_time)
  );
  if (blocks.length === 0) return "";
  const rows = blocks.map((b) => {
    const start = timeLabel(b.start_time) ?? "--:--";
    const end = timeLabel(b.end_time) ?? "--:--";
    const typeLabel = BLOCK_TYPE_LABELS[b.block_type] ?? b.block_type;
    const emoji = BLOCK_TYPE_EMOJI[b.block_type] ?? "⏱";
    const title = b.affair_title ? escapeHtml(b.affair_title) : "";
    const typeWithTitle = title ? `${emoji} ${typeLabel} · ${title}` : `${emoji} ${typeLabel}`;
    const energy = b.energy_cost ? ` · ${b.energy_cost}⚡` : "";
    return [
      `<div style="display:flex;justify-content:space-between;align-items:center;padding:3px 0;border-bottom:1px solid var(--vscode-panel-border,#d0d7de);border-bottom-style:dashed;">`,
      `<span style="font-size:0.9em;">`,
      `<span style="${MUTED_STYLE};font-variant-numeric:tabular-nums;">${start}-${end}</span> `,
      `${typeWithTitle}`,
      `</span>`,
      `<span style="display:flex;align-items:center;white-space:nowrap;">${statusBadge(b.status)}${energy ? `<span style="${MUTED_STYLE};font-size:0.8em;margin-left:4px;">${energy}</span>` : ""}</span>`,
      `</div>`,
    ].join("");
  });
  return [
    `<div style="${SECTION_TITLE_STYLE}">今日时间线</div>`,
    ...rows,
  ].join("");
}

function renderCheckins(checkins: RhythmDashboard["checkins"]): string {
  if (!checkins) return "";
  const parts: string[] = [];

  if (checkins.precepts.length > 0) {
    parts.push(`<div style="${SECTION_TITLE_STYLE}">戒律打卡</div>`);
    parts.push(
      ...checkins.precepts.map((c) => {
        const done = c.done_today;
        const result = done
          ? `${RESULT_EMOJI[c.last_result ?? "kept"] ?? "✅"} ${c.last_result ?? "已打卡"}`
          : "待核销";
        return [
          `<div style="display:flex;justify-content:space-between;padding:2px 0;font-size:0.9em;">`,
          `<span>${escapeHtml(c.affair.title)}</span>`,
          `<span style="${MUTED_STYLE}">${result}</span>`,
          `</div>`,
        ].join("");
      })
    );
  }

  if (checkins.habits.length > 0) {
    parts.push(`<div style="${SECTION_TITLE_STYLE}">习惯打卡</div>`);
    parts.push(
      ...checkins.habits.map((c) => {
        const count = c.week_done_count ?? 0;
        const target = c.week_target ?? 0;
        const done = c.done_today;
        const result = done
          ? `${RESULT_EMOJI[c.last_result ?? "done"] ?? "✅"} 已做`
          : "今日待做";
        return [
          `<div style="display:flex;justify-content:space-between;padding:2px 0;font-size:0.9em;">`,
          `<span>${escapeHtml(c.affair.title)}</span>`,
          `<span style="${MUTED_STYLE}">${result} · ${count}/${target}</span>`,
          `</div>`,
        ].join("");
      })
    );
  }

  return parts.join("");
}

function renderPriorities(priorities: PriorityAffair[]): string {
  if (priorities.length === 0) return "";
  const rows = priorities.map((p) => {
    const a = p.affair;
    const stars = importanceStars(a.importance);
    const energy = a.energy_cost ? ` · ${a.energy_cost}⚡` : "";
    const slot = p.suggested_slot ? ` · ${escapeHtml(p.suggested_slot)}` : "";
    return [
      `<div style="padding:4px 0;border-bottom:1px solid var(--vscode-panel-border,#d0d7de);border-bottom-style:dashed;font-size:0.9em;">`,
      `<div style="display:flex;justify-content:space-between;align-items:center;">`,
      `<span><strong>${escapeHtml(a.title)}</strong></span>`,
      `<span>${domainBadge(a.domain)}${stateBadge(a.state)}</span>`,
      `</div>`,
      `<div style="${MUTED_STYLE};font-size:0.85em;margin-top:2px;">`,
      `${stars}${energy}${slot}`,
      `</div>`,
      p.reason
        ? `<div style="${MUTED_STYLE};font-size:0.85em;margin-top:2px;">💡 ${escapeHtml(p.reason)}</div>`
        : "",
      `</div>`,
    ].join("");
  });
  return [
    `<div style="${SECTION_TITLE_STYLE}">优先级事务</div>`,
    ...rows,
  ].join("");
}

function renderNotes(items: string[], kind: "insight" | "warning"): string {
  if (items.length === 0) return "";
  const emoji = kind === "warning" ? "⚠️" : "💡";
  const bg =
    kind === "warning"
      ? "var(--vscode-inputValidation-warningBackground, rgba(234,179,8,0.08))"
      : "var(--vscode-inputValidation-infoBackground, rgba(59,130,246,0.08))";
  const border =
    kind === "warning"
      ? "var(--vscode-inputValidation-warningBorder, #eab308)"
      : "var(--vscode-inputValidation-infoBorder, #3b82f6)";
  const rows = items.map(
    (item) =>
      `<div style="padding:3px 0;font-size:0.85em;">${emoji} ${escapeHtml(item)}</div>`
  );
  return [
    `<div style="${SECTION_TITLE_STYLE};margin-top:10px;">${kind === "warning" ? "警告" : "洞察"}</div>`,
    `<div style="padding:6px 8px;border:1px solid ${border};border-radius:6px;background:${bg};">`,
    ...rows,
    `</div>`,
  ].join("");
}

export function renderRhythmDashboardCard(dashboard: RhythmDashboard): string {
  const dateLabel = formatDateLabel(dashboard.date);
  const title = `📅 ${escapeHtml(dateLabel)} · ⚡ Rhythm 日程`;
  const footer = `<div style="${MUTED_STYLE}; font-size: 0.8em; margin-top: 8px;">数据来自 sail_server · plan v${dashboard.plan_version}</div>`;

  const sections = [
    renderEnergyBar(dashboard),
    renderDomainBars(dashboard.domain_minutes),
    renderTimeline(dashboard),
    renderCheckins(dashboard.checkins),
    renderPriorities(dashboard.priorities),
    renderNotes(dashboard.insights, "insight"),
    renderNotes(dashboard.warnings, "warning"),
  ].filter(Boolean);

  return [
    `<div class="sail-rhythm-card" style="${CARD_STYLE}">`,
    `<div style="${CARD_TITLE_STYLE}">${title}</div>`,
    ...sections,
    footer,
    `</div>`,
  ].join("");
}

function renderUnavailable(dateStr: string, fallback?: string): string {
  if (fallback) {
    return `<div style="${MUTED_STYLE}">${escapeHtml(fallback)}</div>`;
  }
  return `<div style="${MUTED_STYLE}">📅 ${escapeHtml(formatDateLabel(dateStr))} · 暂无 Rhythm 日程数据</div>`;
}

function renderFetchError(dateStr: string, error: string): string {
  return [
    `<div class="sail-rhythm-card" style="${CARD_STYLE}">`,
    `<div style="${CARD_TITLE_STYLE}">📅 ${escapeHtml(formatDateLabel(dateStr))} · ⚡ Rhythm 日程</div>`,
    `<div style="${MUTED_STYLE}">获取失败：${escapeHtml(error)}</div>`,
    `</div>`,
  ].join("");
}

// ---------------------------------------------------------------------------
// Providers
// ---------------------------------------------------------------------------

type RhythmProviderDeps = RhythmCoreDeps & {
  client: SailServerRhythmClient;
  cache: RhythmCache;
};

async function queryDayDashboard(
  deps: RhythmProviderDeps,
  dateStr: string
): Promise<RhythmDashboard> {
  const baseUrl = deps.resolveBaseUrl().replace(/\/+$/, "");
  const cached = deps.cache.get(baseUrl, dateStr);
  if (cached) return cached;
  const data = await deps.client.getDayDashboard(dateStr);
  if (data.error) {
    deps.log?.("warn", `[rhythm] query ${dateStr} failed: ${data.error}`);
  } else {
    deps.cache.set(baseUrl, dateStr, data);
  }
  return data;
}

async function renderRhythmForDate(
  deps: RhythmProviderDeps,
  dateStr: string,
  fallback?: string
): Promise<string> {
  const dashboard = await queryDayDashboard(deps, dateStr);
  if (dashboard.error) return renderFetchError(dateStr, dashboard.error);
  if (dashboard.blocks.length === 0 && dashboard.priorities.length === 0) {
    return renderUnavailable(dateStr, fallback);
  }
  return renderRhythmDashboardCard(dashboard);
}

function resolveCacheTtlMs(deps: RhythmCoreDeps): number {
  return deps.resolveCacheTtlMs?.() ?? DEFAULT_RHYTHM_CACHE_TTL_MS;
}

export function createRhythmDashboardProvider(
  deps: RhythmProviderDeps
): NotePageElementProvider {
  return {
    key: "RHYTHM_DASHBOARD",
    title: "Rhythm Dashboard",
    description:
      "显示指定日期（date 参数 / 笔记日期 / 今天）的 Rhythm 日程仪表板，数据来自 sail_server",
    usage: '<sail-elem key="RHYTHM_DASHBOARD" date="2026-07-18" />',
    cacheTtlMs: resolveCacheTtlMs(deps),
    render: async (ctx: PageElementRenderContext) => {
      const dateArg = ctx.args?.date;
      const dateStr =
        typeof dateArg === "string" && DATE_ARG_REGEX.test(dateArg)
          ? dateArg
          : journalDateStr(ctx.fname) ?? todayDateStr();
      return renderRhythmForDate(deps, dateStr, ctx.fallback);
    },
  };
}

export function createRhythmJournalPrefixProvider(
  deps: RhythmProviderDeps
): NotePageElementProvider {
  return {
    key: "RHYTHM_PREFIX",
    title: "Rhythm Journal Prefix",
    description:
      "Daily Journal 笔记顶部自动显示该日 Rhythm 日程卡片，其他笔记显示帮助",
    usage: '<sail-elem key="RHYTHM_PREFIX" />',
    cacheTtlMs: resolveCacheTtlMs(deps),
    render: async (ctx: PageElementRenderContext) => {
      const dateStr = journalDateStr(ctx.fname);
      if (dateStr) {
        return renderRhythmForDate(deps, dateStr, ctx.fallback);
      }
      if (deps.renderPrefixHelp) {
        return deps.renderPrefixHelp(ctx);
      }
      return [
        `<div class="sail-page-element-help" style="${MUTED_STYLE}">`,
        `Sail Page Element: <code>${escapeHtml(ctx.raw)}</code> renders dynamic content for the top area of the note.`,
        `</div>`,
      ].join("");
    },
  };
}

// ---------------------------------------------------------------------------
// Core factory
// ---------------------------------------------------------------------------

export type RhythmCore = {
  client: SailServerRhythmClient;
  cache: RhythmCache;
  createRhythmDashboardProvider: () => NotePageElementProvider;
  createRhythmJournalPrefixProvider: () => NotePageElementProvider;
  clearCache: () => void;
  register: (registry: PageElementRegistry) => void;
};

export function createRhythmCore(deps: RhythmCoreDeps): RhythmCore {
  const cache = createRhythmCache({
    resolveTtlMs: () => resolveCacheTtlMs(deps),
  });
  const client = createSailServerRhythmClient({
    resolveBaseUrl: deps.resolveBaseUrl,
    fetchImpl: deps.fetchImpl,
  });
  const providerDeps: RhythmProviderDeps = { ...deps, client, cache };
  return {
    client,
    cache,
    createRhythmDashboardProvider: () =>
      createRhythmDashboardProvider(providerDeps),
    createRhythmJournalPrefixProvider: () =>
      createRhythmJournalPrefixProvider(providerDeps),
    clearCache: () => cache.clear(),
    register: (registry: PageElementRegistry) => {
      registry.register(createRhythmDashboardProvider(providerDeps), {
        override: true,
      });
      registry.register(createRhythmJournalPrefixProvider(providerDeps), {
        override: true,
      });
      deps.log?.("info", "[rhythm] page element providers registered");
    },
  };
}
