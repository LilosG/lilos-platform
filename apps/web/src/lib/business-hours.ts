/* Professional GBP regularHours formatter for the Governance UI.

   Handles the Google Business Profile normalized_profile["regularHours"]
   structure:

   periods: [{ openDay, openTime, closeDay, closeTime }]

   openTime / closeTime may be either:
   - string: "09:00"
   - object: { hours: 9 }
   - object: { hours: 9, minutes: 0, seconds: 0, nanos: 0 }

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

interface GbpTimeOfDay {
  hours?: unknown;
  minutes?: unknown;
  seconds?: unknown;
  nanos?: unknown;
}

interface Period {
  openDay: string;
  openTime: string | GbpTimeOfDay;
  closeDay: string;
  closeTime: string | GbpTimeOfDay;
}

interface Interval {
  open: number;
  close: number;
}

interface DaySchedule {
  intervals: Interval[];
}

const MIDNIGHT_MINUTES = 24 * 60;

function parseTime(raw: string | GbpTimeOfDay): number | null {
  if (typeof raw === "string") {
    if (!/^\d{1,2}:\d{2}$/.test(raw)) return null;
    const parts = raw.split(":");
    const hours = Number.parseInt(parts[0], 10);
    const minutes = Number.parseInt(parts[1], 10);
    if (Number.isNaN(hours) || Number.isNaN(minutes)) return null;
    if (hours < 0 || hours > 23) return null;
    if (minutes < 0 || minutes > 59) return null;
    return hours * 60 + minutes;
  }

  if (raw === null || typeof raw !== "object") return null;

  const hours =
    typeof raw.hours === "number" ? raw.hours : Number(raw.hours ?? NaN);
  const minutes =
    typeof raw.minutes === "number" ? raw.minutes : Number(raw.minutes ?? 0);
  const seconds =
    typeof raw.seconds === "number" ? raw.seconds : Number(raw.seconds ?? 0);
  const nanos =
    typeof raw.nanos === "number" ? raw.nanos : Number(raw.nanos ?? 0);

  if (Number.isNaN(hours) || Number.isNaN(minutes)) return null;
  if (hours < 0 || hours > 23) return null;
  if (minutes < 0 || minutes > 59) return null;
  if (seconds < 0 || seconds > 59) return null;
  if (nanos < 0 || nanos > 999_999_999) return null;

  return hours * 60 + minutes;
}

function formatAmPm(minutes: number): string {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  if (h === 24) return "12:00 AM";
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

export interface BusinessHoursRow {
  dayLabel: string;
  timeLabel: string;
}

function buildScheduleRows(schedules: DaySchedule[]): BusinessHoursRow[] {
  if (schedules.length !== 7) return [];
  const rows: BusinessHoursRow[] = [];
  let i = 0;
  while (i < 7) {
    const current = schedules[i];
    if (current.intervals.length === 0) {
      let j = i;
      while (j < 7 && schedules[j].intervals.length === 0) j++;
      const dayLabel =
        j - i === 1
          ? DAY_ABBREV[i as DayIndex]
          : `${DAY_ABBREV[i as DayIndex]}\u2013${DAY_ABBREV[(j - 1) as DayIndex]}`;
      rows.push({ dayLabel, timeLabel: "Closed" });
      i = j;
      continue;
    }
    let j = i + 1;
    while (j < 7 && intervalsEqual(current, schedules[j])) j++;
    const timeLabel = current.intervals.map(formatInterval).join(", ");
    const dayLabel =
      j - i === 1
        ? DAY_ABBREV[i as DayIndex]
        : `${DAY_ABBREV[i as DayIndex]}\u2013${DAY_ABBREV[(j - 1) as DayIndex]}`;
    rows.push({ dayLabel, timeLabel });
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
      typeof (p as Period).closeDay === "string" &&
      typeof (p as Period).openTime !== "undefined" &&
      typeof (p as Period).closeTime !== "undefined",
  );
}

export function formatBusinessHoursRows(
  value: unknown,
): BusinessHoursRow[] | null {
  if (!value || typeof value !== "object") return null;
  const obj = value as Record<string, unknown>;
  if (!isValidPeriods(obj.periods)) return null;

  const periods = obj.periods as Period[];
  const schedules: DaySchedule[] = Array.from({ length: 7 }, () => ({
    intervals: [],
  }));

  for (const p of periods) {
    const openIdx = DAY_INDEX[p.openDay];
    const closeIdx = DAY_INDEX[p.closeDay];
    if (openIdx === undefined || closeIdx === undefined) return null;

    const openMinutes = parseTime(p.openTime);
    const closeMinutes = parseTime(p.closeTime);
    if (openMinutes === null || closeMinutes === null) return null;

    if (openIdx === closeIdx) {
      if (closeMinutes <= openMinutes) {
        schedules[openIdx].intervals.push({
          open: openMinutes,
          close: MIDNIGHT_MINUTES,
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
      schedules[openIdx].intervals.push({
        open: openMinutes,
        close: MIDNIGHT_MINUTES,
      });
      let day = (openIdx + 1) % 7;
      while (day !== closeIdx) {
        schedules[day].intervals.push({ open: 0, close: MIDNIGHT_MINUTES });
        day = (day + 1) % 7;
      }
      schedules[closeIdx].intervals.push({ open: 0, close: closeMinutes });
    }
  }

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

  const fullOpen: DaySchedule = {
    intervals: [{ open: 0, close: MIDNIGHT_MINUTES }],
  };
  const closed: DaySchedule = { intervals: [] };
  for (let d = 0; d < 7; d++) {
    if (intervalsEqual(schedules[d], fullOpen)) {
      schedules[d] = fullOpen;
    } else if (intervalsEqual(schedules[d], closed)) {
      schedules[d] = closed;
    }
  }

  return buildScheduleRows(schedules);
}

export function formatBusinessHours(value: unknown): string {
  const rows = formatBusinessHoursRows(value);
  if (!rows || rows.length === 0) return "\u2014";
  return rows.map((r) => `${r.dayLabel}\t${r.timeLabel}`).join("\n");
}

// ---------------------------------------------------------------------------
// Entering hours by hand
// ---------------------------------------------------------------------------

/**
 * business.hours could only ever be derived from a connected Google Business
 * Profile sync. Connecting a provider happens after activation, and activation
 * waits on the business details — so a client with no GBP connection yet had a
 * required detail marked Missing with no way in the product to supply it.
 *
 * These build the same shape a GBP sync produces, so a manually entered
 * schedule and a synced one are indistinguishable downstream and render
 * through the same formatter.
 */

export const BUSINESS_DAYS = [
  "MONDAY",
  "TUESDAY",
  "WEDNESDAY",
  "THURSDAY",
  "FRIDAY",
  "SATURDAY",
  "SUNDAY",
] as const;

export type BusinessDay = (typeof BUSINESS_DAYS)[number];

export interface BusinessHoursDayInput {
  day: BusinessDay;
  closed: boolean;
  /** 24-hour "HH:MM". */
  open: string;
  close: string;
}

export interface BusinessHoursBuildResult {
  value: { periods: Period[] } | null;
  errors: string[];
}

const TIME_PATTERN = /^([01]\d|2[0-3]):([0-5]\d)$/;

function minutesOf(time: string): number | null {
  const match = TIME_PATTERN.exec(time.trim());
  if (!match) return null;
  return Number(match[1]) * 60 + Number(match[2]);
}

function dayLabel(day: BusinessDay): string {
  return day.charAt(0) + day.slice(1).toLowerCase();
}

/**
 * Convert a per-day schedule into GBP `regularHours` periods.
 *
 * A closing time at or before the opening time is read as closing after
 * midnight and rolls the close onto the following day, which is how Google
 * models it and how a bar that shuts at 2am has to be expressed. Anything that
 * cannot be read is reported rather than guessed at, because a silently wrong
 * opening hour is worse than a refusal.
 */
export function buildBusinessHoursValue(
  days: BusinessHoursDayInput[],
): BusinessHoursBuildResult {
  const errors: string[] = [];
  const periods: Period[] = [];

  for (const entry of days) {
    if (entry.closed) continue;
    const open = minutesOf(entry.open);
    const close = minutesOf(entry.close);
    if (open === null || close === null) {
      errors.push(
        `${dayLabel(entry.day)}: enter both times as HH:MM, 24-hour.`,
      );
      continue;
    }
    const openIndex = BUSINESS_DAYS.indexOf(entry.day);
    const closesNextDay = close <= open;
    const closeDay = closesNextDay
      ? BUSINESS_DAYS[(openIndex + 1) % BUSINESS_DAYS.length]
      : entry.day;
    periods.push({
      openDay: entry.day,
      openTime: entry.open.trim(),
      closeDay,
      closeTime: entry.close.trim(),
    });
  }

  if (errors.length === 0 && periods.length === 0) {
    errors.push(
      "Set opening times for at least one day, or the client has no hours.",
    );
  }
  return { value: errors.length === 0 ? { periods } : null, errors };
}
