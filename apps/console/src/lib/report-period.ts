/**
 * Report periods and comparisons: whole calendar months only, as first-of-month dates.
 * Pure month arithmetic and addresses; every word shown to a person lives in report-view.ts.
 */
export const MAX_PERIOD_MONTHS = 12;
/** A period of 1 to 12 consecutive whole months, each given as "YYYY-MM-01". */
export interface PeriodRef {
  start: string;
  end: string;
}
/** What a period is compared with. A baseline names its own months. */
export type ComparisonRef =
  | { kind: "previous" }
  | { kind: "year-ago" }
  | { kind: "baseline"; start: string; end: string };
export const PREVIOUS: ComparisonRef = { kind: "previous" };
/** The typed reasons a period or comparison is refused, the API's own codes. */
export type PeriodErrorCode =
  | "REPORT_MONTH_NOT_ENDED"
  | "REPORT_PERIOD_ORDER"
  | "REPORT_PERIOD_TOO_LONG"
  | "REPORT_BASELINE_OVERLAPS";
const MONTH = /^(\d{4})-(0[1-9]|1[0-2])$/;
const ISO_MONTH = /^(\d{4})-(0[1-9]|1[0-2])-01$/;
const index = (iso: string) => {
  const match = ISO_MONTH.exec(iso);
  return match ? Number(match[1]) * 12 + Number(match[2]) - 1 : NaN;
};
const fromIndex = (value: number) =>
  `${Math.floor(value / 12)}-${String((value % 12) + 1).padStart(2, "0")}-01`;
export const isMonth = (iso: string) => ISO_MONTH.test(iso);
/** "2026-09-01" moved by whole months (negative is earlier). */
export const addMonths = (iso: string, count: number) =>
  fromIndex(index(iso) + count);
/** How many months a period spans; both ends included. */
export const span = (period: PeriodRef) =>
  index(period.end) - index(period.start) + 1;
/** Every first-of-month date from start to end. */
export const monthsOf = (period: PeriodRef): string[] =>
  Array.from({ length: span(period) }, (_, i) => addMonths(period.start, i));
/** "2026-09" for one month, "2026-05_2026-09" for several. */
export const periodSlug = (period: PeriodRef) =>
  period.start === period.end
    ? period.start.slice(0, 7)
    : `${period.start.slice(0, 7)}_${period.end.slice(0, 7)}`;
/** The period an address names; null when it is not 1 to 12 whole months in order. */
export function periodFromSlug(slug: string): PeriodRef | null {
  const [first, last, ...rest] = slug.split("_");
  if (
    rest.length ||
    !MONTH.test(first) ||
    (last !== undefined && !MONTH.test(last))
  )
    return null;
  const period = { start: `${first}-01`, end: `${last ?? first}-01` };
  const months = span(period);
  return months >= 1 && months <= MAX_PERIOD_MONTHS ? period : null;
}
export const comparisonSlug = (comparison: ComparisonRef) =>
  comparison.kind === "previous"
    ? "previous"
    : comparison.kind === "year-ago"
      ? "year-ago"
      : `vs-${periodSlug(comparison)}`;
/** The ?vs= value: previous, year-ago, or the baseline months. */
export const comparisonQuery = (comparison: ComparisonRef) =>
  comparison.kind === "baseline"
    ? periodSlug(comparison)
    : comparisonSlug(comparison);
/** The comparison a ?vs= names; no value is the default, an unknown one is null. */
export function comparisonFromQuery(vs: string | null): ComparisonRef | null {
  if (vs === null || vs === "" || vs === "previous") return PREVIOUS;
  if (vs === "year-ago") return { kind: "year-ago" };
  const baseline = periodFromSlug(vs);
  return baseline
    ? { kind: "baseline", start: baseline.start, end: baseline.end }
    : null;
}
/** The comparison as the API's request body. */
export function comparisonBody(comparison: ComparisonRef) {
  if (comparison.kind === "previous") return { basis: "previous_period" };
  if (comparison.kind === "year-ago") return { basis: "same_period_last_year" };
  return {
    basis: "custom_baseline",
    baseline_start: comparison.start,
    baseline_end: comparison.end,
  };
}
/** The comparison a stored report names. */
export function comparisonOfSpec(spec: {
  basis: "previous_period" | "same_period_last_year" | "custom_baseline";
  baseline_start?: string | null;
  baseline_end?: string | null;
}): ComparisonRef {
  if (spec.basis === "previous_period") return PREVIOUS;
  if (spec.basis === "same_period_last_year") return { kind: "year-ago" };
  return {
    kind: "baseline",
    start: spec.baseline_start ?? "",
    end: spec.baseline_end ?? "",
  };
}
export const samePeriod = (a: PeriodRef, b: PeriodRef) =>
  a.start === b.start && a.end === b.end;
export const sameComparison = (a: ComparisonRef, b: ComparisonRef) =>
  comparisonSlug(a) === comparisonSlug(b);
/** The address of a report: /clients/<slug>/reports/<period>/ with the comparison and revision. */
export function reportHref(
  client: string,
  period: PeriodRef,
  comparison: ComparisonRef = PREVIOUS,
  options: { revision?: number; document?: boolean } = {},
) {
  const query = new URLSearchParams();
  if (comparison.kind !== "previous")
    query.set("vs", comparisonQuery(comparison));
  if (options.revision) query.set("revision", String(options.revision));
  const text = query.toString();
  return `/clients/${client}/reports/${periodSlug(period)}/${options.document ? "document/" : ""}${text ? `?${text}` : ""}`;
}
/** Why a period cannot be reported, or null. Mirrors the API's own checks. */
export function periodError(
  period: PeriodRef,
  lastEnded: string,
): PeriodErrorCode | null {
  if (index(period.end) > index(lastEnded)) return "REPORT_MONTH_NOT_ENDED";
  if (index(period.end) < index(period.start)) return "REPORT_PERIOD_ORDER";
  if (span(period) > MAX_PERIOD_MONTHS) return "REPORT_PERIOD_TOO_LONG";
  return null;
}
/** Why a baseline cannot be used with a period, or null. */
export function baselineError(
  baseline: PeriodRef,
  period: PeriodRef,
): PeriodErrorCode | null {
  if (index(baseline.end) < index(baseline.start)) return "REPORT_PERIOD_ORDER";
  if (span(baseline) > MAX_PERIOD_MONTHS) return "REPORT_PERIOD_TOO_LONG";
  if (index(baseline.end) >= index(period.start))
    return "REPORT_BASELINE_OVERLAPS";
  return null;
}
/** The months a report can end on: ended months, newest first. */
export const selectableMonths = (lastEnded: string, count = 36): string[] =>
  Array.from({ length: count }, (_, i) => addMonths(lastEnded, -i));
export type PresetId = "last-month" | "last-3" | "last-6" | "year-to-date";
/** The quick choices, as periods ending on the last month that has ended. */
export function presetPeriods(lastEnded: string): Record<PresetId, PeriodRef> {
  const january = `${lastEnded.slice(0, 4)}-01-01`;
  return {
    "last-month": { start: lastEnded, end: lastEnded },
    "last-3": { start: addMonths(lastEnded, -2), end: lastEnded },
    "last-6": { start: addMonths(lastEnded, -5), end: lastEnded },
    "year-to-date": { start: january, end: lastEnded },
  };
}
