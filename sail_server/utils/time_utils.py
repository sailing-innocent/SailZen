from datetime import datetime, timedelta
from typing import Tuple, List
from dataclasses import dataclass


@dataclass
class Week:
    start: datetime
    end: datetime


@dataclass
class QuarterBiWeek:
    index: int  # index of a quater
    first_w: Week
    next_w: Week


def getQuarterFromMonth(month: int) -> int:
    return (month - 1) // 3 + 1


def getQuarterStartEnd(
    year: int, quater: int
) -> Tuple[datetime, datetime]:
    # check q in [1, 4]
    if quater < 1 or quater > 4:
        raise ValueError("Quarter must be in [1, 4]")
    # get the start and end of the quarter
    start_date = datetime(year, (quater - 1) * 3 + 1, 1)
    end_date = datetime(year, quater * 3, 1)
    return start_date, end_date


def startOfISOWeek(date: datetime) -> datetime:
    # get the start of the ISO week
    return date - timedelta(days=date.weekday())


def endOfISOWeek(date: datetime) -> datetime:
    # get the end of the ISO week
    return date + timedelta(days=6 - date.weekday())


def isWithIn(
    date: datetime, start_date: datetime, end_date: datetime
) -> bool:
    return date >= start_date and date <= end_date


def listFullWeeksInQuarter(year: int, quarter: int) -> List[Week]:
    qStart, qEnd = getQuarterStartEnd(year, quarter)
    cursor = startOfISOWeek(qStart)
    # find the first "full week" in a quater
    while not isWithIn(cursor, qStart, qEnd) or not isWithIn(
        endOfISOWeek(cursor), qStart, qEnd
    ):
        cursor = cursor + timedelta(days=7)
        if cursor > qEnd:
            break
    weeks = []
    # iterate to append all of the "full weeks" in a quater
    while isWithIn(cursor, qStart, qEnd) and isWithIn(
        endOfISOWeek(cursor), qStart, qEnd
    ):
        weeks.append(Week(start=cursor, end=endOfISOWeek(cursor)))
        cursor = cursor + timedelta(days=7)
    return weeks


def listFullBiweeksInQuarter(year: int, quarter: int) -> List[QuarterBiWeek]:
    weeks = listFullWeeksInQuarter(year, quarter)
    biweeks = []
    idx = 0
    for i in range(0, len(weeks), 2):
        idx = idx + 1
        biweeks.append(QuarterBiWeek(index=idx, first_w=weeks[i], next_w=weeks[i + 1]))
    return biweeks


# QBWTime, Quarter BiWeek Time
class QuarterBiWeekTime:
    # The timepoint defined a whole biweek in a quater, it can be proved that every quater has 6 biweeks
    # So that we can use string `YYYY-Q[1-3]-B[1-6]` to represent the timepoint
    def __init__(self, year: int, quarter: int, biweek: int):
        self.year = year
        self.quarter = quarter
        self.biweek = biweek
        self.start_date, self.end_date = getQuarterStartEnd(year, quarter)

    @classmethod
    def from_datetime(cls, t: datetime):
        cls.year = t.year
        cls.quater = getQuarterFromMonth(t.month)
        for biweek in listFullBiweeksInQuarter(cls.year, cls.quarter):
            if isWithIn(t, biweek.first_w.start, biweek.next_w.end):
                cls.biweek = biweek.index
        return cls

    @classmethod
    def from_timestamp(cls, timestamp: int):
        t = datetime.fromtimestamp(timestamp)
        return cls.from_datetime(t)

    def to_db_int(self):
        return self.year * 10000 + self.quarter * 100 + self.biweek

    @classmethod
    def from_db_int(cls, value: int):
        cls.year = value // 10000
        cls.quarter = (value % 10000) // 100
        cls.biweek = value % 100
        cls.start_date, cls.end_date = getQuarterStartEnd(cls.year, cls.quarter)
        return cls

    def __repr__(self):
        # serialize to "YYYY-[1-3]-[1-6]"
        return f"{self.year}-{self.quarter}-{self.biweek}"

    def __str__(self):
        return self.__repr__()

    def __eq__(self, other):
        return (
            self.year == other.year
            and self.quarter == other.quarter
            and self.biweek == other.biweek
        )

    def __hash__(self):
        return hash((self.year, self.quarter, self.biweek))
