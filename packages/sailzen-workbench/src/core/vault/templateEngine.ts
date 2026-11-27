import * as fs from "fs";
import * as path from "path";
import { parseNoteContent, serializeNewNote } from "./noteModel";

const DEFAULT_DAILY_BODY = `## Plan

## Record

## Summary

## Note
`;

/**
 * Format a YYYY-MM-DD Date into journal.daily.YYYY.MM.DD.
 */
export function formatDailyJournalFname(date: Date = new Date()): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `journal.daily.${y}.${m}.${d}`;
}

export function formatIsoDate(date: Date = new Date()): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

/** Parse journal.daily.YYYY.MM.DD into a Date, or null if not a daily note. */
export function parseDateFromDailyFname(fname: string): Date | null {
  const m = fname.match(/(?:^|\.)(\d{4})\.(\d{2})\.(\d{2})$/);
  if (!m) return null;
  const year = Number(m[1]);
  const month = Number(m[2]);
  const day = Number(m[3]);
  const d = new Date(year, month - 1, day);
  if (d.getFullYear() !== year || d.getMonth() !== month - 1 || d.getDate() !== day) {
    return null;
  }
  return d;
}

/** ISO day of week: Monday=1 .. Sunday=7 (matches D:/vault/notes/routines.weekday.N). */
export function getIsoDayOfWeek(date: Date): number {
  const jsDay = date.getDay();
  return jsDay === 0 ? 7 : jsDay;
}

/** Render Dendron-compatible daily/note template body. */
export function renderTemplateBody(
  templateBody: string,
  fname: string,
  title: string,
  date: Date = new Date()
): string {
  const targetDate = parseDateFromDailyFname(fname) ?? date;
  const dow = String(getIsoDayOfWeek(targetDate));
  const isoDate = formatIsoDate(targetDate);

  return templateBody
    .replace(/\{\{\s*getDayOfWeek\s*\(\s*fnameToDate\s*\)\s*\}\}/g, dow)
    .replace(/\{\{\s*DATE\s*\}\}/gi, isoDate)
    .replace(/\{\{\s*TITLE\s*\}\}/gi, title)
    .replace(/\{\{\s*FNAME\s*\}\}/gi, fname);
}

/** Build full markdown content for a new daily journal note, respecting templates.daily.md if present. */
export async function buildDailyJournalContent(
  notesDir: string,
  date: Date = new Date()
): Promise<{ fname: string; content: string }> {
  const fname = formatDailyJournalFname(date);
  const title = formatIsoDate(date);
  let bodyTemplate = DEFAULT_DAILY_BODY;

  const tplPath = path.join(notesDir, "templates.daily.md");
  try {
    const rawTpl = await fs.promises.readFile(tplPath, "utf8");
    const parsed = parseNoteContent("templates.daily", rawTpl);
    if (parsed.body.trim().length > 0) {
      bodyTemplate = parsed.body;
    }
  } catch {
    // Use default template body when templates.daily.md is absent
  }

  const renderedBody = renderTemplateBody(bodyTemplate, fname, title, date);
  const content = serializeNewNote({
    fname,
    title,
    body: renderedBody,
    traitIds: ["journalNote"],
  });
  return { fname, content };
}
