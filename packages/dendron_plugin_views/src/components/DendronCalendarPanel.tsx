import React, { useCallback, useState } from "react";
import {
  CalendarViewMessageType,
  ConfigUtils,
  DMessageSource,
  NoteProps,
  Time,
  VaultUtils,
} from "@saili/common-all";
import { createLogger } from "../utils/logger";
import { engineHooks } from "../features/engine";
import {
  BadgeProps,
  Badge,
  Button,
  CalendarProps,
  Divider,
  Calendar
} from "antd";
import _ from "lodash";
import { DendronProps, DendronComponent } from "../types";
import { postVSCodeMessage } from "../utils/vscode";
import generateCalendar, { SelectInfo } from "antd/lib/calendar/generateCalendar";
import dayjs, { Dayjs } from "dayjs";

const getListData = (value: Dayjs) => {
  let listData: { type: string; content: string }[] = []; // Specify the type of listData
  switch (value.date()) {
    case 8:
      listData = [
        // { type: 'warning', content: 'This is warning event.' },
        // { type: 'success', content: 'This is usual event.' },
      ];
      break;
    case 10:
      listData = [
        // { type: 'warning', content: 'This is warning event.' },
        // { type: 'success', content: 'This is usual event.' },
        // { type: 'error', content: 'This is error event.' },
      ];
      break;
    case 15:
      listData = [
        // { type: 'warning', content: 'This is warning event' },
        // { type: 'success', content: 'This is very long usual event......' },
        // { type: 'error', content: 'This is error event 1.' },
        // { type: 'error', content: 'This is error event 2.' },
        // { type: 'error', content: 'This is error event 3.' },
        // { type: 'error', content: 'This is error event 4.' },
      ];
      break;
    default:
  }
  return listData || [];
};

const getMonthData = (value: Dayjs) => {
  if (value.date() === 8) {
    return 1394;
  }
};

const DendronCalendarPanel: DendronComponent = (props: DendronProps) => {
  // -- init
  const ctx = "CalenderView";
  const logger = createLogger("calendarView");
  
  // Use actual config from engine, fallback to default config
  const config = props.engine.config || ConfigUtils.genDefaultConfig();
  const journalConfig = ConfigUtils.getJournal(config);
  const journalDailyDomain = journalConfig.dailyDomain;
  const journalName = journalConfig.name;
  
  // Convert Dendron date format (y.MM.dd) to dayjs format (YYYY.MM.DD)
  // Dendron uses: y=year, M=month, d=day (lowercase)
  // dayjs uses: YYYY=year, MM=month, DD=day (uppercase)
  const dendronDateFormat = journalConfig.dateFormat || "y.MM.dd";
  const journalDateFormat = dendronDateFormat
    .replace(/y/g, "YYYY")
    .replace(/M/g, "M")  // dayjs also uses M for month
    .replace(/d/g, "D"); // dayjs uses D for day
  const journalMonthDateFormat = "YYYY.MM"; // TODO compute format for currentMode="year" from config
  
  logger.info({ ctx, journalDailyDomain, journalName, journalDateFormat });

  const monthCellRender = (value: Dayjs) => {
    const num = getMonthData(value);
    return num ? (
      <div className="notes-month">
        <section>{num}</section>
        <span>Backlog number</span>
      </div>
    ) : null;
  };


  const dateCellRender = (value: Dayjs) => {
    const listData = getListData(value);
    return (
      <ul className="events">
        {listData.map((item) => (
          <li key={item.content}>
            <Badge status={item.type as BadgeProps['status']} text={item.content} />
          </li>
        ))}
      </ul>
    );
  };

  const cellRender: CalendarProps<Dayjs>['cellRender'] = (current, info) => {
    if (info.type === 'date') return dateCellRender(current);
    if (info.type === 'month') return monthCellRender(current);
    return info.originNode;
  };

  const getDateKey = useCallback<
    (date: Dayjs, mode: string) => string | undefined
  >(
    (date, mode) => {
      const format =
        mode === "date"
          ? journalDateFormat
          : journalMonthDateFormat;
      return format ? date.format(format) : undefined;
    },
    [journalDateFormat]
  );
  
  const onPanelChange = (value: Dayjs, mode: CalendarProps<Dayjs>['mode']) => {
    // console.log(value.format('YYYY-MM-DD'), mode);
  };

  // mode?: CalendarProps["mode"]
  const onSelect = useCallback<
    (date: Dayjs, info: SelectInfo) => void
  >(
    (date, info) => {
      const dateKey = getDateKey(date, info.source);
      // fname format: dailyDomain.journalName.dateKey (e.g., daily.journal.2025.12.23)
      const fname = `${journalDailyDomain}.${journalName}.${dateKey}`;
      postVSCodeMessage({
        type: CalendarViewMessageType.onSelect,
        data: {
          id: undefined,
          fname,
        },
        source: DMessageSource.webClient,
      });
    },
    [getDateKey, journalDailyDomain, journalName]
  );

  const onClickToday = useCallback(() => {
    const mode = "date";
    onSelect( dayjs(), { source: mode });
  }, [onSelect]);

  return (
    <>
      <div className="vscode-calendar-view">
        <Calendar
          onSelect={onSelect}
          onPanelChange={onPanelChange}
          cellRender={cellRender}
          // dateFullCellRender={dateFullCellRender} // TODO: customize render
          fullscreen={false}
        />
      </div>
      <Divider plain style={{ marginTop: 0 }}>
        <Button type="primary" onClick={onClickToday}>
          Today
        </Button>
      </Divider>
      {/* <button onClick={onClickToday}>Today</button> */}
    </>
  )
}

export default DendronCalendarPanel;