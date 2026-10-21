import type {
  ComparisonBasis,
  CountComparison,
  CountFigure,
  HeadlineKey,
  NarrativeFailureCode,
  NoteCode,
  PortfolioReportRow,
  PortfolioReports,
  RateComparison,
  RateFigure,
  ReportDetail,
  ReportList,
  ReportNote,
  ReportReadiness,
  ReportRevisionRow,
  ReportSnapshot,
  SectionKey,
  UnavailableReason,
} from "../adapters/reports";
import type { GbpMetric } from "../adapters/gbp";
import type { Tile } from "./local-search-view";
import { DISPLAY_TIME_ZONE, clockText, dateText, fmt, signed } from "./present";
import {
  PREVIOUS,
  addMonths,
  comparisonOfSpec,
  reportHref,
  samePeriod,
  type PeriodErrorCode,
  type PeriodRef,
} from "./report-period";
import { reportChips, readinessChips, type Chip } from "./status";
const MONTHS = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
] as const;
const parts = (month: string) => {
  const [year, number] = month.split("-").map(Number);
  return { year, number };
};
/** "September" from "2026-09-01". */
export const monthName = (month: string) => MONTHS[parts(month).number - 1];
/** "September 2026" from "2026-09-01". */
export const monthLabel = (month: string) =>
  `${monthName(month)} ${parts(month).year}`;
/** "Sep" from "2026-09-01": a month in a chart or a narrow table column. */
export const monthShort = (month: string) => monthName(month).slice(0, 3);
/** "September 2026", "May – September 2026", or "November 2025 – February 2026". */
export function periodLabel(period: PeriodRef): string {
  if (period.start === period.end) return monthLabel(period.start);
  const first = parts(period.start);
  const last = parts(period.end);
  return first.year === last.year
    ? `${monthName(period.start)} – ${monthLabel(period.end)}`
    : `${monthLabel(period.start)} – ${monthLabel(period.end)}`;
}
/** "September 1–30, 2026" or "May 1 – September 30, 2026": the days a report covers. */
export function periodRange(period: PeriodRef): string {
  const { year, number } = parts(period.end);
  const last = new Date(Date.UTC(year, number, 0)).getUTCDate();
  if (period.start === period.end)
    return `${monthName(period.end)} 1–${last}, ${year}`;
  const first = parts(period.start);
  return first.year === year
    ? `${monthName(period.start)} 1 – ${monthName(period.end)} ${last}, ${year}`
    : `${monthName(period.start)} 1, ${first.year} – ${monthName(period.end)} ${last}, ${year}`;
}
export const periodOf = (view: {
  start_month: string;
  end_month: string;
}): PeriodRef => ({ start: view.start_month, end: view.end_month });
/** The months a report was compared with, in words: "February – April 2026". */
export const comparedLabel = (snapshot: ReportSnapshot) =>
  periodLabel(periodOf(snapshot.comparison.compared));
/** What the comparison is, for the cover and the document's first page. */
export function comparisonText(snapshot: ReportSnapshot): string {
  const { comparison, period } = snapshot;
  const compared = periodLabel(periodOf(comparison.compared));
  const single = period.start_month === period.end_month;
  if (comparison.basis === "previous_period")
    return `${single ? "the month before" : "the months before"} (${compared})`;
  if (comparison.basis === "same_period_last_year")
    return `${single ? "the same month last year" : "the same months last year"} (${compared})`;
  return `${compared}, a baseline of ${comparison.compared_as === "monthly_average" ? "a different length, as monthly averages" : "the same length"}`;
}
/** "the monthly average of February – April 2026", or just the months, as a change is worded. */
export function comparedPhrase(comparison: {
  compared_as: "total" | "monthly_average";
  compared: PeriodRef;
}): string {
  const label = periodLabel(comparison.compared);
  return comparison.compared_as === "monthly_average"
    ? `the monthly average of ${label}`
    : label;
}
/** "June 2026", "June to August 2026" or "May 2026 to February 2027": months, as a range. */
export function coveredRange(covered: readonly string[]): string {
  const first = covered[0];
  const last = covered[covered.length - 1];
  if (!first || !last) return "the months with data";
  if (first === last) return monthLabel(first);
  return parts(first).year === parts(last).year
    ? `${monthName(first)} to ${monthLabel(last)}`
    : `${monthLabel(first)} to ${monthLabel(last)}`;
}
/** The months Search Console's comparison covers, when it covers fewer than the compared period. */
export const searchCoveredMonths = (snapshot: ReportSnapshot) =>
  snapshot.notes.find(
    (item) => item.code === "search_console_compared_as_average",
  )?.covered_months ?? null;
/** What each "Compare with" choice means, shown under the choice. */
export const compareHelp = {
  previous: "The same number of months immediately before the report.",
  "year-ago": "The same months one year earlier.",
  baseline:
    "Months you choose, ending before the report starts. A baseline of another length is compared as monthly averages.",
} as const;
export const basisText: Record<ComparisonBasis, string> = {
  previous_period: "Previous period",
  same_period_last_year: "Same period last year",
  custom_baseline: "A baseline period",
};
/** The comparison a stored report names, in a few words for lists and chips. */
export function comparisonName(spec: ReportRevisionRow["comparison"]): string {
  if (spec.basis === "previous_period") return "vs previous period";
  if (spec.basis === "same_period_last_year") return "vs same period last year";
  return `vs ${periodLabel({ start: spec.baseline_start ?? "", end: spec.baseline_end ?? "" })}`;
}
export const reportChip = (status: keyof typeof reportChips): Chip =>
  reportChips[status];
export const readinessChip = (readiness: ReportReadiness): Chip =>
  readinessChips[readiness];
/** Why a figure has no number, in the words a person reads. Never an enum value. */
export const reasonText: Record<UnavailableReason, string> = {
  not_connected: "Not connected",
  not_synced: "Not synced yet",
  no_data: "No data reported",
  not_reported: "Not reported by Google",
  partial_period: "Only part of the period",
  no_views: "No profile views",
  not_tracked: "Not tracked yet",
  not_compared: "No comparison",
  source_unavailable: "Unavailable",
  no_search_data_yet: "No search data yet",
};
/** A figure that can be stated: available or partial, with a value. */
export const present = (figure: CountFigure | RateFigure | null | undefined) =>
  !!figure &&
  figure.availability !== "unavailable" &&
  figure.value !== null &&
  figure.value !== undefined;
export const isPartial = (
  figure: CountFigure | RateFigure | null | undefined,
) => !!figure && figure.availability === "partial";
/** A count, with an asterisk when it covers only part of the period; null when there is none. */
export const countText = (
  figure: CountFigure | null | undefined,
): string | null =>
  figure && present(figure)
    ? `${fmt(figure.value as number)}${isPartial(figure) ? "*" : ""}`
    : null;
export const rateText = (
  figure: RateFigure | null | undefined,
  format: (value: number) => string,
): string | null =>
  figure && present(figure)
    ? `${format(figure.value as number)}${isPartial(figure) ? "*" : ""}`
    : null;
/** The words for a figure that has no number: its reason, or a plain fallback. */
export const gapText = (
  figure: CountFigure | RateFigure | null | undefined,
): string => (figure?.reason ? reasonText[figure.reason] : "Not available");
export const percentText = (value: number) => `${value.toFixed(1)}%`;
export const ratingText = (value: number) => value.toFixed(1);
const pointsText = (value: number, unit: string) =>
  `${value > 0 ? "+" : value < 0 ? "−" : ""}${Math.abs(value).toFixed(1)} ${unit}`;
const absoluteChange = (change: number) =>
  `${change > 0 ? "+" : change < 0 ? "−" : ""}${fmt(Math.abs(change))}`;
/** "+244 (+20.0%)": a count's change, or null when no change can be stated. */
export function changeText(
  comparison: CountComparison,
  versus: "compared" | "year" = "compared",
): string | null {
  const change = versus === "year" ? comparison.year_change : comparison.change;
  const percent =
    versus === "year"
      ? comparison.year_change_percent
      : comparison.change_percent;
  if (change === null || change === undefined) return null;
  const share =
    percent === null || percent === undefined ? null : signed(percent, 1);
  return share
    ? `${absoluteChange(change)} (${share})`
    : absoluteChange(change);
}
/** Up, down or flat, for colouring a change. */
export const directionOf = (
  change: number | null | undefined,
): "up" | "down" | "flat" | "none" =>
  change === null || change === undefined
    ? "none"
    : change > 0
      ? "up"
      : change < 0
        ? "down"
        : "flat";
export type Better = "higher" | "lower";
export type Tone = "good" | "bad" | "neutral";
/** Whether a change helped: the arrow follows the number, the colour follows what is better. */
export const toneOf = (
  direction: "up" | "down" | "flat" | "none",
  better: Better = "higher",
): Tone =>
  direction === "up" || direction === "down"
    ? (direction === "up") === (better === "higher")
      ? "good"
      : "bad"
    : "neutral";
const round = (value: number | null | undefined) =>
  value === null || value === undefined ? null : Math.round(value);
/** A tile for one count against its comparison; a missing figure is a muted tile, never 0. */
export function comparisonTile(
  label: string,
  comparison: CountComparison,
  snapshot: ReportSnapshot,
  format: (value: number) => string = fmt,
): Tile {
  const current = comparison.current;
  if (!present(current))
    return {
      label,
      value: "Unavailable",
      description: gapText(current),
      trend: null,
      missing: true,
    };
  const value = format(current.value as number);
  if (isPartial(current))
    return {
      label,
      value: `${value}*`,
      description: partialText(current),
      trend: null,
      missing: false,
    };
  const against = comparedPhrase({
    compared_as: comparison.compared_as,
    compared: periodOf(snapshot.comparison.compared),
  });
  return {
    label,
    value,
    description:
      comparison.change_percent === null ||
      comparison.change_percent === undefined
        ? present(comparison.compared)
          ? `Same as ${against}`
          : `No ${against} to compare`
        : `vs ${against}`,
    trend: round(comparison.change_percent),
    missing: false,
  };
}
/** How much of the period a partial figure covers, in words. */
export function partialText(figure: CountFigure | RateFigure): string {
  const count = figure as CountFigure;
  if (count.months_covered != null && count.months_expected != null)
    return `Partial · ${count.months_covered} of ${count.months_expected} months synced`;
  if (count.days_covered != null && count.days_expected != null)
    return `Partial · ${count.days_covered} of ${count.days_expected} days synced`;
  return "Partial period";
}
export const metricLabel = (metric: GbpMetric) => METRIC_LABEL[metric];
const METRIC_LABEL: Record<GbpMetric, string> = {
  BUSINESS_IMPRESSIONS_DESKTOP_MAPS: "Google Maps on desktop",
  BUSINESS_IMPRESSIONS_DESKTOP_SEARCH: "Google Search on desktop",
  BUSINESS_IMPRESSIONS_MOBILE_MAPS: "Google Maps on mobile",
  BUSINESS_IMPRESSIONS_MOBILE_SEARCH: "Google Search on mobile",
  CALL_CLICKS: "Calls",
  WEBSITE_CLICKS: "Website clicks",
  BUSINESS_DIRECTION_REQUESTS: "Direction requests",
  BUSINESS_CONVERSATIONS: "Conversations",
  BUSINESS_BOOKINGS: "Bookings",
  BUSINESS_FOOD_ORDERS: "Food orders",
  BUSINESS_FOOD_MENU_CLICKS: "Menu clicks",
};
/** Lower-case form of a figure's name, for use inside a sentence. */
export const metricSentenceName = (metric: GbpMetric) =>
  metricLabel(metric).toLowerCase();
export interface HeadlineCard {
  key: HeadlineKey;
  label: string;
  value: string;
  /** "+20.0% vs February – April 2026". */
  change: string;
  direction: "up" | "down" | "flat";
  tone: Tone;
  /** What the figure is, in one plain sentence. */
  line: string;
}
const HEADLINE: Record<HeadlineKey, { label: string; line: string }> = {
  profile_views: {
    label: "Profile views",
    line: "Times people saw your business on Google Search and Google Maps.",
  },
  profile_actions: {
    label: "Profile actions",
    line: "Calls, website clicks and direction requests from your Google profile.",
  },
  website_search_clicks: {
    label: "Website search clicks",
    line: "Times people clicked through to your website from Google Search.",
  },
  organic_sessions: {
    label: "Visits from search",
    line: "Website visits that began with an unpaid Google search.",
  },
  new_reviews: {
    label: "New reviews",
    line: "Google reviews customers wrote during this period.",
  },
  average_rating: {
    label: "Average rating",
    line: "Your average Google star rating across all reviews.",
  },
};
/** The headline cards, from the figures the API chose. Words only; no number is computed here. */
export function headlineCards(snapshot: ReportSnapshot): HeadlineCard[] {
  const against = (as: "total" | "monthly_average") =>
    comparedPhrase({
      compared_as: as,
      compared: periodOf(snapshot.comparison.compared),
    });
  // Search Console may cover only some of the compared months: the tile names those months.
  const covered = searchCoveredMonths(snapshot);
  return snapshot.headlines.flatMap((item): HeadlineCard[] => {
    const copy = HEADLINE[item.key];
    if (item.count) {
      const { count } = item;
      const comparedTo =
        item.key === "website_search_clicks" &&
        count.compared_as === "monthly_average" &&
        covered?.length
          ? `the monthly average of ${coveredRange(covered)}`
          : against(count.compared_as);
      if (!present(count.current) || count.change === null) return [];
      return [
        {
          key: item.key,
          label: copy.label,
          value: fmt(count.current.value as number),
          change: `${signed(count.change_percent ?? null, 1) ?? absoluteChange(count.change as number)} vs ${comparedTo}`,
          direction: directionOf(count.change) as "up" | "down" | "flat",
          tone: toneOf(directionOf(count.change)),
          line: copy.line,
        },
      ];
    }
    const rate = item.rate as RateComparison;
    if (
      !present(rate.current) ||
      rate.change === null ||
      rate.change === undefined
    )
      return [];
    return [
      {
        key: item.key,
        label: copy.label,
        value: ratingText(rate.current.value as number),
        change: `${pointsText(rate.change, "stars")} vs ${against("total")}`,
        direction: directionOf(rate.change) as "up" | "down" | "flat",
        tone: toneOf(directionOf(rate.change)),
        line: copy.line,
      },
    ];
  });
}
export const headlineTiles = (snapshot: ReportSnapshot): Tile[] =>
  headlineCards(snapshot).map((card) => ({
    label: card.label,
    value: card.value,
    description: card.change,
    trend: null,
    missing: false,
  }));
const SECTION_LABEL: Record<SectionKey, string> = {
  profile_views: "Profile views",
  profile_actions: "Profile actions",
  daily_series: "Daily activity",
  search_terms: "Search terms",
  locations: "Locations",
  reviews: "Reviews",
  search_console: "Search Console",
  analytics: "Website visits",
  local_rank: "Local ranking",
  work_completed: "Work completed",
  narrative: "Narrative",
};
const plural = (count: number, one: string, many: string) =>
  `${count} ${count === 1 ? one : many}`;
const NOTE_TEXT: Record<NoteCode, (note: ReportNote) => string> = {
  gbp_not_connected: () =>
    "Google Business Profile is not connected, so this report has no profile data.",
  gbp_period_not_synced: () =>
    "No day of this period has been synced from Google Business Profile yet.",
  gbp_period_partial: (note) =>
    note.count
      ? `${plural(note.count, "day", "days")} of this period ${note.count === 1 ? "has" : "have"} not synced from Google yet, so profile totals cover part of the period.`
      : "Part of this period has not synced from Google yet, so profile totals cover part of the period.",
  gbp_sync_failed: () =>
    "The last Business Profile sync did not finish, so some days may be missing.",
  gbp_location_not_mapped: () =>
    "A location is not connected to a Business Profile, so it is not in these totals.",
  gbp_search_terms_unavailable: () =>
    "Google has not published this period’s search terms yet.",
  gbp_compared_period_incomplete: () =>
    "The comparison period is not fully synced, so changes against it are not shown.",
  gbp_year_ago_unavailable: () =>
    "The same months last year are not fully synced, so the yearly comparison is not shown.",
  reviews_not_synced: () =>
    "Reviews have not been synced yet, so review figures are not shown.",
  search_console_not_connected: () =>
    "Search Console is not connected, so search clicks and queries are not shown.",
  search_console_not_synced: () =>
    "Search Console has not delivered this period yet.",
  search_console_lag_days: (note) =>
    note.count
      ? `Google is still finalizing the last ${plural(note.count, "day", "days")} of search data, so those figures may rise.`
      : "Google is still finalizing the last days of search data, so those figures may rise.",
  search_console_months_missing: (note) =>
    note.count
      ? `${plural(note.count, "month", "months")} of search data ${note.count === 1 ? "has" : "have"} not synced yet and ${note.count === 1 ? "is" : "are"} left out of the totals.`
      : "Some months of search data have not synced yet and are left out of the totals.",
  search_console_compared_period_unavailable: () =>
    "Search Console data for the comparison period is not complete, so changes are not shown.",
  search_console_no_data_yet: () =>
    "Search Console has no data for this period yet.",
  search_console_compared_as_average: (note) =>
    `Search Console's comparison covers ${coveredRange(note.covered_months ?? [])} only, so this compares monthly averages.`,
  search_console_first_month_partial: (note) =>
    note.month
      ? `Google's first month of Search Console data (${monthLabel(note.month)}) can be a partial month, so it is not used as a comparison.`
      : "Google's first month of Search Console data can be a partial month, so it is not used as a comparison.",
  analytics_not_connected: () =>
    "Google Analytics is not connected, so website visits are not shown.",
  analytics_not_synced: () =>
    "Google Analytics has not delivered this period yet.",
  analytics_organic_unavailable: () =>
    "Google Analytics cannot report search visits for this website.",
  analytics_months_missing: (note) =>
    note.count
      ? `${plural(note.count, "month", "months")} of website visits ${note.count === 1 ? "has" : "have"} not synced yet and ${note.count === 1 ? "is" : "are"} left out of the totals.`
      : "Some months of website visits have not synced yet and are left out of the totals.",
  analytics_compared_period_unavailable: () =>
    "Analytics data for the comparison period is not complete, so changes are not shown.",
  optional_figure_not_reported: (note) =>
    `Google reported no ${note.metric ? metricSentenceName(note.metric) : "figure"} this period${note.count != null ? ` (${fmt(note.count)} in the comparison period)` : ""}. This can reflect a change in how Google reports it, not lower demand.`,
  optional_figure_stopped: (note) =>
    `Google reported no ${note.metric ? metricSentenceName(note.metric) : "figure"} after ${note.month ? monthName(note.month) : "an earlier month"}, so this period's total is incomplete.`,
};
export const noteText = (note: ReportNote): string =>
  NOTE_TEXT[note.code](note);
export interface NoteGroup {
  section: string;
  notes: string[];
}
export function noteGroups(snapshot: ReportSnapshot): NoteGroup[] {
  const groups = new Map<SectionKey, string[]>();
  for (const note of snapshot.notes)
    groups.set(note.section, [
      ...(groups.get(note.section) ?? []),
      noteText(note),
    ]);
  return [...groups].map(([section, notes]) => ({
    section: SECTION_LABEL[section],
    notes,
  }));
}
/** The chip beside the report's title that opens the data notes. */
export function notesChip(snapshot: ReportSnapshot): Chip {
  const count = snapshot.notes.length;
  return count === 0
    ? { label: "Data complete", tone: "" }
    : {
        label: `${count} data ${count === 1 ? "note" : "notes"}`,
        tone: snapshot.readiness === "missing_data" ? "error" : "warn",
      };
}
export const draftFailureText: Record<NarrativeFailureCode, string> = {
  draft_failed:
    "The draft could not be written right now. Write it by hand or try again.",
  draft_malformed:
    "The draft did not come back in the expected form, so it was not used.",
  draft_empty: "The draft was empty, so it was not used.",
  number_not_in_data:
    "The draft mentioned a number that is not in this report’s data, so it was not used.",
  authorship_mentioned: "The draft mentioned who wrote it, so it was not used.",
  causal_claim:
    "The draft claimed one thing caused another, which the data cannot show, so it was not used.",
  tone_not_supported:
    "The draft called a result good or bad when its figure did not move that way, so it was not used.",
};
/** Why a period or comparison was refused, in words a person can act on. */
export const periodErrorText: Record<PeriodErrorCode, string> = {
  REPORT_MONTH_NOT_ENDED: "A report covers months that have ended.",
  REPORT_PERIOD_ORDER: "The last month cannot be before the first month.",
  REPORT_PERIOD_TOO_LONG: "A report covers 1 to 12 whole months.",
  REPORT_BASELINE_OVERLAPS:
    "The baseline must end before the report period starts.",
};
const FAILURES: Record<string, string> = {
  ...periodErrorText,
  REPORT_MONTH_NOT_FIRST: "A report covers whole calendar months.",
  REPORT_PERIOD_INVALID: "That period is not one this report covers.",
  REPORT_COMPARISON_INVALID: "That comparison is not one this report offers.",
  REPORT_BASELINE_REQUIRED:
    "Choose the first and last month of the baseline period.",
  REPORT_BASELINE_UNEXPECTED: "Baseline months only go with a baseline period.",
  REPORT_NARRATIVE_EMPTY: "Write both narrative sections before approving.",
  REPORT_DATA_MISSING:
    "This report is missing the Business Profile data it needs. Reconnect Google, then generate it again.",
  REPORT_NOT_EDITABLE: "An approved report cannot be edited.",
  REPORT_CARD_FIGURE_UNAVAILABLE:
    "A result card can only be about a figure this report has.",
  REPORT_REVISION_SUPERSEDED:
    "A newer version of this report exists. Reload to see it.",
  REPORT_ALREADY_APPROVED:
    "This report is already approved and the data has not changed.",
  REPORT_NOT_APPROVED: "Approve the report before recording it as sent.",
  REPORT_SENT_DATE_INVALID:
    "Choose a day after the last month ended and not in the future.",
  REPORT_SCOPE_NOT_READABLE:
    "A report covers every active location, and you cannot read all of them.",
  REPORT_NOT_FOUND: "That report no longer exists. Reload the page.",
  PERMISSION_DENIED: "You do not have permission to do that.",
};
/** A sentence a person can act on for a failed report action; never the system's words. */
export const reportFailureText = (code: string): string =>
  FAILURES[code] ??
  "That did not go through. Reload to see the current state, then try again.";
export interface NarrativeView {
  editable: boolean;
  /** The result cards at the top of the document; their figures are fixed, only words change. */
  cards: {
    keys: string;
    tone: string;
    headline: boolean;
    title: string;
    text: string;
  }[];
  sections: { title: string; paragraphs: string[]; field: string }[];
  empty: boolean;
  drafted: boolean;
}
const paragraphs = (text: string) =>
  text
    .split(/\n{2,}/)
    .map((part) => part.trim())
    .filter(Boolean);
export const narrativeParagraphs = paragraphs;
export function narrativeView(report: ReportDetail): NarrativeView {
  const narrative = report.narrative;
  return {
    editable:
      report.status === "draft" &&
      report.is_current &&
      report.permissions.can_generate,
    sections: [
      {
        title: "What changed and why",
        paragraphs: paragraphs(narrative.what_changed),
        field: "what_changed",
      },
      {
        title: "Next work",
        paragraphs: paragraphs(narrative.next_work),
        field: "next_work",
      },
    ],
    empty: !narrative.what_changed.trim() || !narrative.next_work.trim(),
    drafted: narrative.origin === "hermes",
    cards: narrative.result_cards.map((card) => ({
      keys: card.figure_keys.join(","),
      tone: card.tone,
      headline: card.headline,
      title: card.title,
      text: card.text,
    })),
  };
}
export interface ReportActions {
  approve: { allowed: boolean; why: string | null };
  send: { allowed: boolean; why: string | null };
}
/** What the person may do with this revision right now, and why a button is off. */
export function reportActions(report: ReportDetail): ReportActions {
  const can = report.permissions.can_publish;
  const approvable =
    report.status === "draft" &&
    report.is_current &&
    report.readiness !== "missing_data" &&
    !narrativeView(report).empty;
  return {
    approve: {
      allowed: can && approvable,
      why: !can
        ? "Only an owner or administrator can approve a report."
        : report.status !== "draft"
          ? null
          : !report.is_current
            ? "A newer version of this report exists."
            : report.readiness === "missing_data"
              ? "Business Profile data is missing for this period."
              : narrativeView(report).empty
                ? "Write both narrative sections first."
                : null,
    },
    send: {
      allowed: can && report.status === "ready",
      why: !can
        ? "Only an owner or administrator can record a report as sent."
        : report.status === "draft"
          ? "Approve the report first."
          : null,
    },
  };
}
/** The report's period and comparison, as they appear in its address. */
export const reportRef = (report: ReportDetail) => ({
  period: periodOf(report.period),
  comparison: comparisonOfSpec(report.comparison),
});
export const headline = (report: ReportDetail) =>
  `${periodLabel(periodOf(report.period))} performance report`;
export interface Confirm {
  title: string;
  lines: string[];
  accept: string;
}
/** The exact period and client an approval or a send applies to. */
export function approveCopy(client: string, period: PeriodRef): Confirm {
  return {
    title: "Approve this report?",
    lines: [
      `${client} · ${periodLabel(period)} (${periodRange(period)}).`,
      "Once approved, its numbers and wording are locked. If the data changes later, a new draft is made and this one stays as approved.",
      "Approving does not send anything to the client.",
    ],
    accept: "Approve report",
  };
}
export function sendCopy(
  client: string,
  period: PeriodRef,
  sentOn: string,
): Confirm {
  return {
    title: "Record this report as sent?",
    lines: [
      `${client} · ${periodLabel(period)} (${periodRange(period)}).`,
      `You are recording that you sent it to the client on ${dateText(sentOn)}. LILOs does not email the report.`,
    ],
    accept: "Record as sent",
  };
}
/** The first day a report can be recorded as sent: the day after its last month ends. */
export const earliestSendDay = (period: PeriodRef) => addMonths(period.end, 1);
export const portfolioFilters = [
  ["all", "All reports"],
  ["needs_attention", "Needs attention"],
  ["missing_data", "Missing data"],
  ["ready", "Ready"],
  ["sent", "Sent"],
  ["not_generated", "Not generated"],
] as const;
export type PortfolioFilter = (typeof portfolioFilters)[number][0];
/** The filter from the query string; anything unknown is refused, not ignored. */
export function parsePortfolioFilter(
  value: string | null,
): PortfolioFilter | null {
  if (value === null || value === "") return "all";
  return portfolioFilters.find(([key]) => key === value)?.[0] ?? null;
}
const matchesFilter = (row: PortfolioReportRow, filter: PortfolioFilter) =>
  filter === "all" ||
  (filter === "not_generated" && row.status === null) ||
  (filter === "sent" && row.status === "sent") ||
  (row.status !== "sent" &&
    row.status !== null &&
    ((filter === "ready" && row.readiness === "ready") ||
      (filter === "needs_attention" && row.readiness === "ready_with_note") ||
      (filter === "missing_data" && row.readiness === "missing_data")));
export interface PortfolioRowView {
  slug: string;
  name: string;
  period: string;
  status: Chip;
  readiness: Chip | null;
  delivery: string;
  href: string;
  action: string;
}
const NOT_GENERATED: Chip = { label: "Not generated", tone: "neutral" };
export function portfolioRows(
  view: PortfolioReports,
  filter: PortfolioFilter,
): PortfolioRowView[] {
  return view.clients
    .filter((row) => matchesFilter(row, filter))
    .map((row) => ({
      slug: row.slug,
      name: row.name,
      period: monthLabel(row.month),
      status: row.status ? reportChip(row.status) : NOT_GENERATED,
      readiness: row.readiness ? readinessChip(row.readiness) : null,
      delivery: row.sent_on
        ? `Sent ${dateText(row.sent_on)}`
        : row.status === null
          ? "Not generated"
          : "Not sent yet",
      href: row.status
        ? reportHref(row.slug, { start: row.month, end: row.month }, PREVIOUS)
        : `/clients/${row.slug}/reports/`,
      action: row.status ? "View report" : "Open reports",
    }));
}
export function portfolioTiles(view: PortfolioReports): Tile[] {
  const total = view.clients.length;
  const tile = (label: string, count: number, description: string): Tile => ({
    label,
    value: String(count),
    description,
    trend: null,
    missing: false,
  });
  const period = monthLabel(view.month);
  return [
    tile("Reports ready", view.counts.ready, `${period} · data complete`),
    tile(
      "Need attention",
      view.counts.needs_attention,
      `${period} · ready with a data note`,
    ),
    tile(
      "Missing data",
      view.counts.missing_data,
      `${period} · cannot be approved yet`,
    ),
    tile(
      "Sent",
      view.counts.sent,
      `of ${total} ${total === 1 ? "client" : "clients"}`,
    ),
  ];
}
/** "Nov 1, 8:00 AM Pacific": when a scheduled run happens, in the agency's time zone. */
export function runText(iso: string): string {
  const at = new Date(iso);
  const day = new Intl.DateTimeFormat("en-US", {
    timeZone: DISPLAY_TIME_ZONE,
    month: "short",
    day: "numeric",
  }).format(at);
  const time = new Intl.DateTimeFormat("en-GB", {
    timeZone: DISPLAY_TIME_ZONE,
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(at);
  return `${day}, ${clockText(time)} Pacific`;
}
export interface HistoryRowView {
  period: string;
  comparison: string;
  version: string | null;
  status: Chip;
  readiness: Chip;
  delivered: string;
  href: string;
  current: boolean;
}
/** Every stored revision, newest period first. A report with several shows which version it is. */
export function historyRows(list: ReportList, slug: string): HistoryRowView[] {
  const key = (row: ReportRevisionRow) =>
    `${row.period.start_month}|${row.period.end_month}|${row.comparison.basis}|${row.comparison.baseline_start ?? ""}`;
  const perReport = new Map<string, number>();
  for (const row of list.history)
    perReport.set(key(row), (perReport.get(key(row)) ?? 0) + 1);
  return list.history.map((row: ReportRevisionRow) => ({
    period: periodLabel(periodOf(row.period)),
    comparison: comparisonName(row.comparison),
    version:
      (perReport.get(key(row)) ?? 0) > 1 ? `Version ${row.revision}` : null,
    status: reportChip(row.status),
    readiness: readinessChip(row.readiness),
    delivered: row.delivery ? dateText(row.delivery.sent_on) : "Not sent yet",
    href: reportHref(
      slug,
      periodOf(row.period),
      comparisonOfSpec(row.comparison),
      { revision: row.revision },
    ),
    current: row.is_current,
  }));
}
export interface CurrentPanel {
  title: string;
  heading: string;
  text: string;
  status: Chip | null;
  readiness: Chip | null;
  action: { label: string; href: string } | null;
  generate: boolean;
  blocked: boolean;
}
export function currentPanel(list: ReportList, slug: string): CurrentPanel {
  const month = list.current_month;
  const name = monthName(month);
  const current = list.current;
  const title = `Current report · ${monthLabel(month)}`;
  if (!current)
    return {
      title,
      heading: `${name} report has not been generated`,
      text: list.upcoming
        ? `It is drafted automatically ${runText(list.upcoming.next_run_at)}. You can also generate it now from the data already collected.`
        : "You can generate it now from the data already collected.",
      status: null,
      readiness: null,
      action: null,
      generate: list.permissions.can_generate,
      blocked: false,
    };
  const text: Record<ReportRevisionRow["status"], string> = {
    draft: `Review the numbers, write the narrative, then approve it.`,
    ready: "Approved. Send it to the client, then record when you did.",
    sent: current.delivery
      ? `Sent ${dateText(current.delivery.sent_on)}.`
      : "Sent.",
  };
  return {
    title,
    heading:
      current.status === "draft"
        ? `${name} performance report is ready to review`
        : current.status === "ready"
          ? `${name} performance report is approved`
          : `${name} performance report was sent`,
    text: text[current.status],
    status: reportChip(current.status),
    readiness: readinessChip(current.readiness),
    action: {
      label: "Open current report",
      href: reportHref(slug, periodOf(current.period), PREVIOUS, {
        revision: current.revision,
      }),
    },
    generate: false,
    blocked: current.readiness === "missing_data",
  };
}
export interface UpcomingRow {
  title: string;
  text: string;
}
export function upcomingRows(list: ReportList): UpcomingRow[] {
  const next = list.upcoming;
  if (!next) return [];
  const { year, number } = parts(next.month);
  const last = new Date(Date.UTC(year, number, 0)).getUTCDate();
  return [
    {
      title: `${monthName(next.month)} performance report`,
      text: `Data through ${monthName(next.month)} ${last} · Draft prepared ${runText(next.next_run_at)}`,
    },
  ];
}
export { samePeriod };
