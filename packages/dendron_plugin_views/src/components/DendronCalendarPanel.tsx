import React, { useCallback, useMemo, useState } from "react";
import {
  CalendarViewMessageType,
  ConfigUtils,
  DMessageSource,
  NoteProps,
} from "@saili/common-all";
import { createLogger } from "../utils/logger";
import { engineHooks } from "../features/engine";
import { DendronProps, DendronComponent } from "../types";
import { postVSCodeMessage } from "../utils/vscode";
import dayjs, { Dayjs } from "dayjs";

const { useEngineAppSelector } = engineHooks;

type DayMeta = {
  noteId?: string;
  markers: ScheduleMarker[];
};

type ScheduleMarker = {
  type: "important" | "holiday" | "event" | "range-start" | "range-end";
  label?: string;
  color?: string;
};

// Users can annotate daily journal notes with schedule markers on their own lines:
//   @important
//   @holiday: Spring Festival
//   @event: Team meeting
//   @event[#ff6600]: Stand-up
//   @range-start: Vacation
//   @range-end: Vacation
const MARKER_RE =
  /^@(important|holiday|event|range-start|range-end)(?:\[([^\]]+)\])?(?:\s*:\s*(.*))?$/m;

function parseMarkers(body: string): ScheduleMarker[] {
  const markers: ScheduleMarker[] = [];
  for (const line of body.split("\n")) {
    const m = line.trim().match(MARKER_RE);
    if (m) {
      markers.push({ type: m[1] as ScheduleMarker["type"], color: m[2], label: m[3]?.trim() });
    }
  }
  return markers;
}

function buildFname(
  date: Dayjs,
  journalName: string,
  journalDailyDomain: string,
  journalDateFormat: string
): string {
  return `${journalName}.${journalDailyDomain}.${date.format(journalDateFormat)}`;
}

const MARKER_COLORS: Record<ScheduleMarker["type"], string> = {
  important: "var(--cal-marker-important, #e55)",
  holiday: "var(--cal-marker-holiday, #4c9)",
  event: "var(--cal-marker-event, #48f)",
  "range-start": "var(--cal-marker-range, #f80)",
  "range-end": "var(--cal-marker-range, #f80)",
};

function MarkerDots({ markers }: { markers: ScheduleMarker[] }) {
  if (!markers.length) return null;
  const seen = new Set<string>();
  const dots: React.ReactNode[] = [];
  for (const m of markers) {
    if (seen.has(m.type)) continue;
    seen.add(m.type);
    const color = m.color ?? MARKER_COLORS[m.type];
    dots.push(
      <span
        key={m.type}
        title={m.label ?? m.type}
        style={{
          display: "inline-block",
          width: 5,
          height: 5,
          borderRadius: "50%",
          background: color,
          margin: "0 1px",
        }}
      />
    );
  }
  return (
    <span style={{ display: "flex", justifyContent: "center", marginTop: 1 }}>
      {dots}
    </span>
  );
}

const WEEKDAYS = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"];

const MONTH_NAMES = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

const DendronCalendarPanel: DendronComponent = (props: DendronProps) => {
  const logger = createLogger("calendarView");

  const config = props.engine.config || ConfigUtils.genDefaultConfig();
  const journalConfig = ConfigUtils.getJournal(config);
  const journalDailyDomain = journalConfig.dailyDomain;
  const journalName = journalConfig.name;
  const dendronDateFormat = journalConfig.dateFormat || "y.MM.dd";
  const journalDateFormat = dendronDateFormat.replace(/y/g, "YYYY").replace(/d/g, "D");

  const getToday = () => dayjs();
  const [viewDate, setViewDate] = useState<Dayjs>(getToday);
  const [mode, setMode] = useState<"month" | "year">("month");

  const notes = useEngineAppSelector((state) => state.engine.notes);
  const noteFName = useEngineAppSelector((state) => state.engine.noteFName);

  const dayMeta = useMemo<Record<string, DayMeta>>(() => {
    if (mode !== "month") return {};
    const year = viewDate.year();
    const month = viewDate.month(); // dayjs month() is 0-indexed
    const meta: Record<string, DayMeta> = {};
    for (let d = 1; d <= viewDate.daysInMonth(); d++) {
      const fname = buildFname(
        dayjs(new Date(year, month, d)),
        journalName, journalDailyDomain, journalDateFormat
      );
      const ids = noteFName[fname];
      if (ids?.length) {
        const note = notes[ids[0]] as NoteProps | undefined;
        meta[d] = { noteId: ids[0], markers: note?.body ? parseMarkers(note.body) : [] };
      }
    }
    return meta;
  }, [viewDate, mode, noteFName, notes, journalName, journalDailyDomain, journalDateFormat]);

  const monthMeta = useMemo<Record<number, boolean>>(() => {
    if (mode !== "year") return {};
    const year = viewDate.year();
    const meta: Record<number, boolean> = {};
    for (let m = 0; m < 12; m++) {
      const daysInMonth = dayjs(new Date(year, m, 1)).daysInMonth();
      for (let d = 1; d <= daysInMonth; d++) {
        const fname = buildFname(
          dayjs(new Date(year, m, d)),
          journalName, journalDailyDomain, journalDateFormat
        );
        if (noteFName[fname]?.length) { meta[m] = true; break; }
      }
    }
    return meta;
  }, [viewDate, mode, noteFName, journalName, journalDailyDomain, journalDateFormat]);

  const prevPeriod = useCallback(() => {
    setViewDate((v) => mode === "month" ? v.subtract(1, "month") : v.subtract(1, "year"));
  }, [mode]);
  const nextPeriod = useCallback(() => {
    setViewDate((v) => mode === "month" ? v.add(1, "month") : v.add(1, "year"));
  }, [mode]);
  const goToday = useCallback(() => {
    const now = dayjs();
    setViewDate(now);
    setMode("month");
    const fname = buildFname(now, journalName, journalDailyDomain, journalDateFormat);
    const ids = noteFName[fname];
    const noteId = ids?.length ? ids[0] : undefined;
    postVSCodeMessage({
      type: CalendarViewMessageType.onSelect,
      data: { id: noteId, fname },
      source: DMessageSource.webClient,
    });
  }, [noteFName, journalName, journalDailyDomain, journalDateFormat]);

  const onSelectDate = useCallback(
    (date: Dayjs) => {
      const fname = buildFname(date, journalName, journalDailyDomain, journalDateFormat);
      const ids = noteFName[fname];
      const noteId = ids?.length ? ids[0] : undefined;
      logger.info({ ctx: "onSelectDate", fname, noteId });
      postVSCodeMessage({
        type: CalendarViewMessageType.onSelect,
        data: { id: noteId, fname },
        source: DMessageSource.webClient,
      });
    },
    [noteFName, journalName, journalDailyDomain, journalDateFormat]
  );

  const onSelectMonth = useCallback(
    (monthIdx: number) => {
      const newDate = viewDate.month(monthIdx).date(1);
      const fname = `${journalName}.${journalDailyDomain}.${newDate.format("YYYY.MM")}`;
      postVSCodeMessage({
        type: CalendarViewMessageType.onSelect,
        data: { id: undefined, fname },
        source: DMessageSource.webClient,
      });
      setViewDate(newDate);
      setMode("month");
    },
    [viewDate, journalName, journalDailyDomain]
  );

  function renderMonthGrid() {
    const year = viewDate.year();
    const month = viewDate.month(); // dayjs month() is 0-indexed
    const firstDay = dayjs(new Date(year, month, 1));
    const startOffset = firstDay.day(); // dayjs day() is 0=Sunday
    const daysInMonth = firstDay.daysInMonth();
    const prevMonthDays = firstDay.subtract(1, "month").daysInMonth();

    const cells: React.ReactNode[] = [];

    for (let i = 0; i < startOffset; i++) {
      cells.push(
        <div key={`prev-${i}`} className="cal-cell cal-cell--other">
          <span className="cal-day-num">{prevMonthDays - startOffset + 1 + i}</span>
        </div>
      );
    }

    for (let d = 1; d <= daysInMonth; d++) {
      const meta = dayMeta[d];
      const isToday = dayjs(new Date(year, month, d)).isSame(dayjs(), "day");
      let cls = "cal-cell";
      if (isToday) cls += " cal-cell--today";
      if (meta?.noteId) cls += " cal-cell--has-note";
      cells.push(
        <div
          key={`day-${d}`}
          className={cls}
          onClick={() => onSelectDate(dayjs(new Date(year, month, d)))}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => e.key === "Enter" && onSelectDate(dayjs(new Date(year, month, d)))}
        >
          <span className="cal-day-num">{d}</span>
          {meta && <MarkerDots markers={meta.markers} />}
        </div>
      );
    }

    const remainder = cells.length % 7;
    if (remainder !== 0) {
      for (let i = 1; i <= 7 - remainder; i++) {
        cells.push(
          <div key={`next-${i}`} className="cal-cell cal-cell--other">
            <span className="cal-day-num">{i}</span>
          </div>
        );
      }
    }

    return (
      <div className="cal-grid">
        {WEEKDAYS.map((w) => <div key={w} className="cal-weekday">{w}</div>)}
        {cells}
      </div>
    );
  }

  function renderYearGrid() {
    const now = dayjs();
    const currentMonth = now.year() === viewDate.year() ? now.month() : -1;
    return (
      <div className="cal-year-grid">
        {MONTH_NAMES.map((name, idx) => {
          let cls = "cal-month-cell";
          if (idx === currentMonth) cls += " cal-month-cell--current";
          if (monthMeta[idx]) cls += " cal-month-cell--has-note";
          return (
            <div
              key={name}
              className={cls}
              onClick={() => onSelectMonth(idx)}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => e.key === "Enter" && onSelectMonth(idx)}
            >
              {name}
              {monthMeta[idx] && <span className="cal-month-dot" />}
            </div>
          );
        })}
      </div>
    );
  }

  const headerLabel = mode === "month" ? viewDate.format("MMMM YYYY") : viewDate.format("YYYY");

  return (
    <div className="cal-root">
      <div className="cal-header">
        <button className="cal-nav-btn" onClick={prevPeriod} title="Previous">&#8249;</button>
        <button
          className="cal-title-btn"
          onClick={() => setMode((m) => (m === "month" ? "year" : "month"))}
          title={mode === "month" ? "Switch to year view" : "Switch to month view"}
        >
          {headerLabel}
        </button>
        <button className="cal-nav-btn" onClick={nextPeriod} title="Next">&#8250;</button>
      </div>

      {mode === "month" ? renderMonthGrid() : renderYearGrid()}

      <div className="cal-footer">
        <button className="cal-today-btn" onClick={goToday}>Today</button>
      </div>
    </div>
  );
};

export default DendronCalendarPanel;