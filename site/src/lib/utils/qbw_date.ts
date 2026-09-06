// QBW Date Utils
// Quarter Biweek Calendar Date Utils

export type DateRange = {
    from: Date | undefined
    to?: Date | undefined
}

export type Week = {
  start: Date
  end: Date
}

export type BiWeek = {
  start: Date
  end: Date
}

export function getQuarterStartEnd(year: number, quarter: number) {
    const q = Math.max(1, Math.min(4, quarter)) - 1
    const startMonth = q * 3
    const start = new Date(year, startMonth, 1)
    const end = new Date(year, startMonth + 3, 0)
    return { start, end }
  }
  
  export function startOfISOWeek(date: Date) {
    const d = new Date(date)
    const day = d.getDay() || 7 // 1..7, Monday=1, Sunday=7
    if (day !== 1) d.setDate(d.getDate() - (day - 1))
    d.setHours(0, 0, 0, 0)
    return d
  }
  
  export function endOfISOWeek(date: Date) {
    const start = startOfISOWeek(date)
    const end = new Date(start)
    end.setDate(start.getDate() + 6)
    end.setHours(23, 59, 59, 999)
    return end
  }
  
  export function isWithin(date: Date, start: Date, end: Date) {
    return date.getTime() >= start.getTime() && date.getTime() <= end.getTime()
  }
  
  export function addDays(date: Date, days: number) {
    const d = new Date(date)
    d.setDate(d.getDate() + days)
    return d
  }
  
  export function formatYMD(date: Date) {
    const y = date.getFullYear()
    const m = `${date.getMonth() + 1}`.padStart(2, '0')
    const d = `${date.getDate()}`.padStart(2, '0')
    return `${y}-${m}-${d}`
  }
  
  export function listFullWeeksInQuarter(year: number, quarter: number) : Week[] {
    const { start: qStart, end: qEnd } = getQuarterStartEnd(year, quarter)
    // find first ISO week whose full span is within the quarter
    let cursor = startOfISOWeek(qStart)
    // advance to first week fully inside
    while (!(isWithin(cursor, qStart, qEnd) && isWithin(endOfISOWeek(cursor), qStart, qEnd))) {
      cursor = addDays(cursor, 7)
      if (cursor > qEnd) break
    }
  
    const weeks: Week[] = []
    while (isWithin(cursor, qStart, qEnd) && isWithin(endOfISOWeek(cursor), qStart, qEnd)) {
      weeks.push({ start: new Date(cursor), end: endOfISOWeek(cursor) })
      cursor = addDays(cursor, 7)
    }
    return weeks
  }
  
  export function listFullBiweeksInQuarter(year: number, quarter: number) : BiWeek[] {
    const weeks = listFullWeeksInQuarter(year, quarter)
    const biweeks: BiWeek[] = []

    for (let i = 0; i + 1 < weeks.length; i += 2) {
      const start = weeks[i].start
      const end = weeks[i + 1].end
      biweeks.push({ start, end })
    }
    return biweeks
  }
  

export function getBiWeek(year: number, quarter: number, index: number) : BiWeek {
    const biweeks = listFullBiweeksInQuarter(year, quarter)
    return biweeks[index - 1]
}

// QBWDate is a class that represents a quarter biweek date
// YYYY-Q-I 
export class QBWDate {
    private year: number 
    private quarter: number
    private index: number 
    private biweek: BiWeek
    
    constructor(year: number, quarter: number, index: number) {
        this.year = year
        this.quarter = quarter
        this.index = index
        this.biweek = getBiWeek(year, quarter, index)
    }
    
    // to_int: return year * 100 + quarter * 10 + index (e.g., 202616)
    to_int() {
        return this.year * 100 + this.quarter * 10 + this.index
    }
    
    // from_int: parse YYYYQQWW format (e.g., 202616 -> year=2026, quarter=1, index=6)
    static from_int(value: number) {
        const year = Math.floor(value / 100)
        const quarter = Math.floor((value % 100) / 10)
        const index = value % 10
        return new QBWDate(year, quarter, index)
    }
    
    // from_date: create QBWDate from a Date object
    static from_date(date: Date): QBWDate {
        const year = date.getFullYear()
        const quarter = Math.floor(date.getMonth() / 3) + 1
        
        // Find which biweek the date belongs to
        const biweeks = listFullBiweeksInQuarter(year, quarter)
        for (let i = 0; i < biweeks.length; i++) {
            const bw = biweeks[i]
            if (date >= bw.start && date <= bw.end) {
                return new QBWDate(year, quarter, i + 1)
            }
        }
        
        // If not found in current quarter, default to first biweek
        return new QBWDate(year, quarter, 1)
    }
    
    get_start_date(): Date {return this.biweek.start}
    get_end_date(): Date {return this.biweek.end}
    get_date_range(): DateRange {return { from: this.biweek.start, to: this.biweek.end }}
    get_quarter(): number {return this.quarter}
    get_index(): number {return this.index}
    get_year(): number {return this.year}
    get_biweek(): BiWeek {return this.biweek}

    get_fmt_string(): string {return `${this.year}年-第${this.quarter}季度-第${this.index}双周`}
}