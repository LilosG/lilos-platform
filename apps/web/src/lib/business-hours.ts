/* Professional GBP regularHours formatter for the Governance UI.

   Handles the Google Business Profile normalized_profile["regularHours"]
   structure:

   { periods: [{ openDay, openTime, closeDay, closeTime }] }

   Falls back gracefully for malformed/unsupported values.
*/

type DayIndex = 0 | 1 | 2 | 3 | 4 | 5 | 6;

const DAY_INDEX: Record<string, DayIndex> = {
  MONDAY: 0,
  TUESDAY: 1,
  WEDNESDAY: 2,
  THURSDAY: 3,
  FRIDAY: 4,
  SATURDAY: 5,
  SUNDAY: 6,
};

const DAY_ABBREV: Record<DayIndex, string> = {
  0: "Mon",
  1: "Tue",
  2: "Wed",
  3: "Thu",
  4: "Fri",
  5: "Sat",
  6: "Sun",
};

interface Period {
  openDay: string;
  openTime: string;
  closeDay: string;
  closeTime: string;
}

interface Interval {
  open: number; // minutes since midnight
  close: number; // minutes since midnight
}

interface DaySchedule {
  intervals: Interval[];
}

function parseTime(raw: string): number {
  const parts = raw?.split(":");
  if (!parts || parts.length !== 2) return 0;
  const hours = Number.parseInt(parts[0], 10);
  const minutes = Number.parseInt(parts[1], 10);
  if (Number.isNaN(hours) || Number.isNaN(minutes)) return 0;
  return hours * 60 + minutes;
}

function formatAmPm(minutes: number): string {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  const period = h >= 12 ? "PM" : "AM";
  const displayHour = h % 12 === 0 ? 12 : h % 12;
  if (m === 0) return `${displayHour}:00 ${period}`;
  return `${displayHour}:${String(m).padStart(2, "0")} ${period}`;
}

function intervalsEqual(a: DaySchedule, b: DaySchedule): boolean {
  if (a.intervals.length !== b.intervals.length) return false;
  return a.intervals.every(
    (intv, idx) =>
      intv.open === b.intervals[idx].open &&
      intv.close === b.intervals[idx].close,
  );
}

function formatInterval(interval: Interval): string {
  return `${formatAmPm(interval.open)}\u2013${formatAmPm(interval.close)}`;
}

function formatSchedulesAsRows(schedules: DaySchedule[]): string[] {
  if (schedules.length !== 7) return [];
  const rows: string[] = [];
  let i = 0;
  while (i < 7) {
    const current = schedules[i];
    if (current.intervals.length === 0) {
      // Collect consecutive closed days.
      let j = i;
      while (j < 7 && schedules[j].intervals.length === 0) j++;
      if (j - i === 1) {
        rows.push(`${DAY_ABBREV[i as DayIndex]}\tClosed`);
      } else {
        rows.push(
          `${DAY_ABBREV[i as DayIndex]}\u2013${DAY_ABBREV[(j - 1) as DayIndex]}\tClosed`,
        );
      }
      i = j;
      continue;
    }
    // Collect consecutive days with identical schedules.
    let j = i + 1;
    while (j < 7 && intervalsEqual(current, schedules[j])) j++;
    const timeLabels = current.intervals.map(formatInterval).join(", ");
    const dayLabel =
      j - i === 1
        ? DAY_ABBREV[i as DayIndex]
        : `${DAY_ABBREV[i as DayIndex]}\u2013${DAY_ABBREV[(j - 1) as DayIndex]}`;
    rows.push(`${dayLabel}\t${timeLabels}`);
    i = j;
  }
  return rows;
}

function isValidPeriods(periods: unknown): periods is Period[] {
  if (!Array.isArray(periods) || periods.length === 0) return false;
  return periods.every(
    (p) =>
      typeof p === "object" &&
      p !== null &&
      typeof (p as Period).openDay === "string" &&
      typeof (p as Period).openTime === "string" &&
      typeof (p as Period).closeDay === "string" &&
      typeof (p as Period).closeTime === "string",
  );
}

export function formatBusinessHours(value: unknown): string {
  if (!value || typeof value !== "object") return "\u2014";
  const obj = value as Record<string, unknown>;
  if (!isValidPeriods(obj.periods)) return "\u2014";

  const periods = obj.periods;

  // Build schedule: 7 days, each with an array of intervals.
  const schedules: DaySchedule[] = Array.from({ length: 7 }, () => ({
    intervals: [],
  }));

  for (const p of periods) {
    const openIdx = DAY_INDEX[p.openDay];
    const closeIdx = DAY_INDEX[p.closeDay];
    if (openIdx === undefined || closeIdx === undefined) return "\u2014";

    const openMinutes = parseTime(p.openTime);
    const closeMinutes = parseTime(p.closeTime);

    if (openIdx === closeIdx) {
      // Same-day interval
      if (closeMinutes <= openMinutes) {
        // Overnight or invalid; treat as 24h/next-day
        // Add to open day until midnight, then continue on next day
        const midnight = 24 * 60;
        schedules[openIdx].intervals.push({
          open: openMinutes,
          close: midnight,
        });
        const nextDay = (openIdx + 1) % 7;
        schedules[nextDay].intervals.push({
          open: 0,
          close: closeMinutes,
        });
      } else {
        schedules[openIdx].intervals.push({
          open: openMinutes,
          close: closeMinutes,
        });
      }
    } else {
      // Multi-day interval (e.g., open Fri, close Mon)
      schedules[openIdx].intervals.push({
        open: openMinutes,
        close: 24 * 60,
      });
      let day = (openIdx + 1) % 7;
      while (day !== closeIdx) {
        schedules[day].intervals.push({ open: 0, close: 24 * 60 });
        day = (day + 1) % 7;
      }
      schedules[closeIdx].intervals.push({ open: 0, close: closeMinutes });
    }
  }

  // Sort and merge overlapping/adjacent intervals per day.
  for (let d = 0; d < 7; d++) {
    if (schedules[d].intervals.length <= 1) continue;
    schedules[d].intervals.sort((a, b) => a.open - b.open);
    const merged: Interval[] = [];
    let current = schedules[d].intervals[0];
    for (let k = 1; k < schedules[d].intervals.length; k++) {
      const next = schedules[d].intervals[k];
      if (next.open <= current.close) {
        current = {
          open: current.open,
          close: Math.max(current.close, next.close),
        };
      } else {
        merged.push(current);
        current = next;
      }
    }
    merged.push(current);
    schedules[d].intervals = merged;
  }

  // Deduplicate full-day schedules for grouping
  const fullOpen: DaySchedule = { intervals: [{ open: 0, close: 24 * 60 }] };
  const closed: DaySchedule = { intervals: [] };
  for (let d = 0; d < 7; d++) {
    if (intervalsEqual(schedules[d], fullOpen)) {
      schedules[d] = fullOpen;
    } else if (intervalsEqual(schedules[d], closed)) {
      schedules[d] = closed;
    }
  }

  const rows = formatSchedulesAsRows(schedules);
  if (rows.length === 0) return "\u2014";
  return rows.join("\n");
}
