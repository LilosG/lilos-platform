import type {
  CountComparison,
  CountFigure,
  NarrativeFailureCode,
  NoteCode,
  PortfolioReportRow,
  PortfolioReports,
  RateFigure,
  ReportDetail,
  ReportList,
  ReportNote,
  ReportReadiness,
  ReportRevisionRow,
  ReportSnapshot,
  SectionKey,
  UnavailableReason,
  WorkKind,
} from "../adapters/reports";
import type { GbpMetric } from "../adapters/gbp";
import { chartModel, type ChartModel, type Tile } from "./local-search-view";
import {
  DISPLAY_TIME_ZONE,
  clockText,
  ctrText,
  dateText,
  fmt,
  positionText,
  signed,
} from "./present";
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
const previousOf = (month: string) => {
  const { year, number } = parts(month);
  return number === 1
    ? `${year - 1}-12-01`
    : `${year}-${String(number - 1).padStart(2, "0")}-01`;
};
/** "September" from "2026-09-01". */
export const monthName = (month: string) => MONTHS[parts(month).number - 1];
/** "September 2026" from "2026-09-01". */
export const monthLabel = (month: string) =>
  `${monthName(month)} ${parts(month).year}`;
/** "September 1–30, 2026": the whole calendar month a report covers. */
export function monthRange(month: string): string {
  const { year, number } = parts(month);
  const last = new Date(Date.UTC(year, number, 0)).getUTCDate();
  return `${monthName(month)} 1–${last}, ${year}`;
}
/** "2026-09" from "2026-09-01": how a month appears in an address. */
export const monthSlug = (month: string) => month.slice(0, 7);
/** "2026-09-01" from "2026-09", or null when it is not a month. */
export const monthFromSlug = (slug: string): string | null =>
  /^\d{4}-(0[1-9]|1[0-2])$/.test(slug) ? `${slug}-01` : null;
export const reportHref = (slug: string, month: string, revision?: number) =>
  `/clients/${slug}/reports/${monthSlug(month)}/${revision ? `?revision=${revision}` : ""}`;
export const summaryHref = (slug: string, month: string, revision?: number) =>
  `/clients/${slug}/reports/${monthSlug(month)}/summary/${revision ? `?revision=${revision}` : ""}`;
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
  partial_period: "Only part of the month",
  no_views: "No profile views",
  not_tracked: "Not tracked yet",
  not_compared: "No comparison",
  source_unavailable: "Unavailable",
};
const MISSING = "–";
const present = (figure: CountFigure | RateFigure) =>
  figure.availability !== "unavailable" &&
  figure.value !== null &&
  figure.value !== undefined;
/** A count, or a dash. A missing figure is never shown as 0. */
export const figureText = (figure: CountFigure | null | undefined): string =>
  figure && present(figure) ? fmt(figure.value as number) : MISSING;
export const rateText = (
  figure: RateFigure | null | undefined,
  format: (value: number) => string,
): string =>
  figure && present(figure) ? format(figure.value as number) : MISSING;
const percentText = (value: number) => `${value.toFixed(1)}%`;
const pointsText = (value: number | null | undefined, unit: string) =>
  value === null || value === undefined
    ? MISSING
    : `${value > 0 ? "+" : value < 0 ? "−" : ""}${Math.abs(value).toFixed(1)} ${unit}`;
const absoluteChange = (change: number | null | undefined) =>
  change === null || change === undefined
    ? null
    : `${change > 0 ? "+" : change < 0 ? "−" : ""}${fmt(Math.abs(change))}`;
const round = (value: number | null | undefined) =>
  value === null || value === undefined ? null : Math.round(value);
const gap = (figure: CountFigure | RateFigure): string =>
  figure.reason ? reasonText[figure.reason] : "Unavailable";
/** A tile for one figure compared with the month before and the same month a year earlier. */
export function comparisonTile(
  label: string,
  comparison: CountComparison,
  month: string,
  format: (value: number) => string = fmt,
): Tile {
  const current = comparison.current;
  if (!present(current))
    return {
      label,
      value: "Unavailable",
      description: gap(current),
      trend: null,
      missing: true,
    };
  const value = format(current.value as number);
  if (current.availability === "partial")
    return {
      label,
      value,
      description:
        current.days_covered != null && current.days_expected != null
          ? `Partial month · ${current.days_covered} of ${current.days_expected} days synced`
          : "Partial month",
      trend: null,
      missing: false,
    };
  const previous = monthName(previousOf(month));
  const year = comparison.year_change_percent;
  const earlier =
    comparison.change_percent === null ||
    comparison.change_percent === undefined
      ? comparison.previous.availability === "unavailable"
        ? `No ${previous} to compare`
        : `Same as ${previous}`
      : `vs ${previous}`;
  return {
    label,
    value,
    description:
      year === null || year === undefined
        ? earlier
        : `${earlier} · ${signed(year, 0)} vs last year`,
    trend: round(comparison.change_percent),
    missing: false,
  };
}
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
export const metricLabel = (metric: GbpMetric) => METRIC_LABEL[metric];
export interface ReportTiles {
  headline: Tile[];
  optional: Tile[];
  rate: Tile;
}
/** Views, calls, website clicks and directions with their trend; optional tiles only when reported. */
export function profileTiles(snapshot: ReportSnapshot): ReportTiles {
  const { gbp, month } = snapshot;
  const action = (metric: GbpMetric) =>
    gbp.actions.actions.find((row) => row.metric === metric)!;
  const rate = gbp.actions.action_rate;
  const rateTile: Tile = !present(rate.current)
    ? {
        label: "Action rate",
        value: "Unavailable",
        description: gap(rate.current),
        trend: null,
        missing: true,
      }
    : {
        label: "Action rate",
        value: percentText(rate.current.value as number),
        description: "Actions per profile view",
        trend: null,
        missing: false,
      };
  return {
    headline: [
      comparisonTile("Profile views", gbp.profile_views.total, month),
      ...(
        [
          "CALL_CLICKS",
          "WEBSITE_CLICKS",
          "BUSINESS_DIRECTION_REQUESTS",
        ] as const
      ).map((metric) =>
        comparisonTile(metricLabel(metric), action(metric).comparison, month),
      ),
    ],
    optional: gbp.actions.optional.map((row) =>
      comparisonTile(metricLabel(row.metric), row.comparison, month),
    ),
    rate: rateTile,
  };
}
export interface SplitRow {
  label: string;
  value: string;
  share: number;
}
export interface SplitView {
  title: string;
  rows: SplitRow[];
}
const SPLIT_LABEL = {
  maps: "Google Maps",
  search: "Google Search",
  desktop: "Desktop",
  mobile: "Mobile",
} as const;
/** Maps/Search and Desktop/Mobile. A split is drawn only when every part is known. */
export function splitViews(snapshot: ReportSnapshot): {
  splits: SplitView[];
  complete: boolean;
} {
  const build = (
    title: string,
    split: ReportSnapshot["gbp"]["profile_views"]["maps_search"],
  ): SplitView | null => {
    const known = split.parts.every(
      (part) =>
        part.figure.availability === "available" &&
        part.share_percent !== null &&
        part.share_percent !== undefined,
    );
    return known
      ? {
          title,
          rows: split.parts.map((part) => ({
            label: SPLIT_LABEL[part.key],
            value: figureText(part.figure),
            share: Math.round(part.share_percent as number),
          })),
        }
      : null;
  };
  const splits = [
    build("Google Maps and Search", snapshot.gbp.profile_views.maps_search),
    build("Desktop and mobile", snapshot.gbp.profile_views.desktop_mobile),
  ].filter((item): item is SplitView => item !== null);
  return { splits, complete: splits.length === 2 };
}
/** The four places a profile view came from, each with its share of all views. */
export function sourceRows(snapshot: ReportSnapshot): SplitRow[] {
  const total = snapshot.gbp.profile_views.total.current;
  return snapshot.gbp.profile_views.sources.flatMap((row) => {
    const current = row.comparison.current;
    if (!present(current)) return [];
    const share =
      total.availability === "available" && total.value
        ? Math.round(((current.value as number) / total.value) * 100)
        : 0;
    return [
      {
        label: metricLabel(row.metric),
        value: fmt(current.value as number),
        share,
      },
    ];
  });
}
export interface DailyCharts {
  views: ChartModel | null;
  actions: ChartModel | null;
  note: string | null;
}
/** Per-day charts from the days that were synced; a day with no data is a gap, not zero. */
export function dailyCharts(snapshot: ReportSnapshot): DailyCharts {
  const { points, missing_days: missing } = snapshot.gbp.daily;
  const series = (key: "views" | "actions") =>
    points.flatMap((point) =>
      point[key] === null ? [] : [{ day: point.day, value: point[key] }],
    );
  return {
    views: chartModel(series("views")),
    actions: chartModel(series("actions")),
    note: missing.length
      ? `${missing.length} ${missing.length === 1 ? "day was" : "days were"} not synced yet and ${missing.length === 1 ? "is" : "are"} left out.`
      : null,
  };
}
export interface TermRow {
  keyword: string;
  value: string;
  bounded: boolean;
}
/** Google reports only "fewer than N" for rare searches; that is shown as "< N", never as 0. */
export function termRows(snapshot: ReportSnapshot): TermRow[] {
  return snapshot.gbp.search_terms.terms.map((term) => ({
    keyword: term.keyword,
    value:
      term.value === null
        ? term.below_threshold === null
          ? MISSING
          : `< ${fmt(term.below_threshold)}`
        : term.below_threshold === null
          ? fmt(term.value)
          : `${fmt(term.value)}+`,
    bounded: !term.is_exact,
  }));
}
export interface ComparisonRow {
  label: string;
  current: string;
  previous: string;
  change: string;
  year: string;
  yearChange: string;
  partial: boolean;
}
const changeText = (comparison: CountComparison, year: boolean): string => {
  const absolute = absoluteChange(
    year ? comparison.year_change : comparison.change,
  );
  const percent = signed(
    (year ? comparison.year_change_percent : comparison.change_percent) ?? null,
    1,
  );
  return absolute === null
    ? MISSING
    : percent
      ? `${absolute} (${percent})`
      : absolute;
};
const countRow = (
  label: string,
  comparison: CountComparison,
): ComparisonRow => ({
  label,
  current: figureText(comparison.current),
  previous: figureText(comparison.previous),
  change: changeText(comparison, false),
  year: figureText(comparison.year_ago),
  yearChange: changeText(comparison, true),
  partial: comparison.current.availability === "partial",
});
/** Every Business Profile figure beside last month and last year: the data behind the tiles. */
export function comparisonRows(snapshot: ReportSnapshot): ComparisonRow[] {
  const { gbp } = snapshot;
  const rate = gbp.actions.action_rate;
  return [
    countRow("Profile views", gbp.profile_views.total),
    ...gbp.profile_views.sources.map((row) =>
      countRow(metricLabel(row.metric), row.comparison),
    ),
    countRow("Actions (calls, website clicks, directions)", gbp.actions.total),
    ...gbp.actions.actions.map((row) =>
      countRow(metricLabel(row.metric), row.comparison),
    ),
    ...gbp.actions.optional.map((row) =>
      countRow(metricLabel(row.metric), row.comparison),
    ),
    {
      label: "Action rate",
      current: rateText(rate.current, percentText),
      previous: rateText(rate.previous, percentText),
      change: pointsText(rate.change, "pts"),
      year: rateText(rate.year_ago, percentText),
      yearChange: pointsText(rate.year_change, "pts"),
      partial: rate.current.availability === "partial",
    },
  ];
}
export interface LocationRow {
  name: string;
  mapped: boolean;
  views: string;
  calls: string;
  website: string;
  directions: string;
  change: string;
}
/** One row per location, only for a client with more than one active location. */
export function locationRows(snapshot: ReportSnapshot): LocationRow[] {
  return snapshot.gbp.locations.map((row) => ({
    name: row.name,
    mapped: row.mapped,
    views: figureText(row.profile_views.current),
    calls: figureText(row.calls.current),
    website: figureText(row.website_clicks.current),
    directions: figureText(row.direction_requests.current),
    change: changeText(row.profile_views, false),
  }));
}
export interface ReviewsView {
  available: boolean;
  gap: string;
  rating: number | null;
  ratingText: string;
  stats: Tile[];
  distribution: { stars: number; count: number; share: number }[];
  total: number;
}
export function reviewsView(snapshot: ReportSnapshot): ReviewsView {
  const reviews = snapshot.reviews;
  if (reviews.availability === "unavailable")
    return {
      available: false,
      gap: reviews.reason ? reasonText[reviews.reason] : "Unavailable",
      rating: null,
      ratingText: MISSING,
      stats: [],
      distribution: [],
      total: 0,
    };
  const total = reviews.distribution_overall.reduce(
    (n, row) => n + row.count,
    0,
  );
  const tile = (label: string, value: string, description: string): Tile => ({
    label,
    value,
    description,
    trend: null,
    missing: value === MISSING,
  });
  return {
    available: true,
    gap: "",
    rating: present(reviews.average_rating_overall)
      ? (reviews.average_rating_overall.value as number)
      : null,
    ratingText: rateText(reviews.average_rating_overall, (n) => n.toFixed(1)),
    stats: [
      tile(
        "New reviews",
        figureText(reviews.new_in_month),
        "Received this month",
      ),
      tile(
        "Average rating this month",
        rateText(reviews.average_rating_in_month, (n) => n.toFixed(1)),
        "Reviews received this month",
      ),
      tile(
        "Responses published",
        figureText(reviews.responses_published),
        "Replies posted this month",
      ),
      tile(
        "Response rate",
        rateText(reviews.response_rate_percent, (n) => `${Math.round(n)}%`),
        "Of this month’s new reviews",
      ),
    ],
    distribution: [...reviews.distribution_overall]
      .sort((a, b) => b.stars - a.stars)
      .map((row) => ({
        stars: row.stars,
        count: row.count,
        share: total ? Math.round((row.count / total) * 100) : 0,
      })),
    total,
  };
}
export interface SearchView {
  available: boolean;
  gap: string;
  tiles: Tile[];
  queries: SearchRow[];
  pages: SearchRow[];
  partialNote: string | null;
}
export interface SearchRow {
  label: string;
  clicks: string;
  impressions: string;
  ctr: string;
  position: string;
  change: string;
}
type SearchNumbers = Omit<
  ReportSnapshot["search_console"]["top_queries"][number],
  "query"
>;
const searchRow = (label: string, row: SearchNumbers): SearchRow => ({
  label,
  clicks: fmt(row.clicks),
  impressions: fmt(row.impressions),
  ctr: row.ctr === null ? MISSING : ctrText(row.ctr),
  position: positionText(row.position),
  change: absoluteChange(row.clicks_change) ?? MISSING,
});
export function searchView(snapshot: ReportSnapshot): SearchView {
  const search = snapshot.search_console;
  const month = snapshot.month;
  if (search.availability === "unavailable")
    return {
      available: false,
      gap: search.reason ? reasonText[search.reason] : "Unavailable",
      tiles: [],
      queries: [],
      pages: [],
      partialNote: null,
    };
  const position = search.average_position;
  const ctr = search.ctr_percent;
  const positionTile: Tile = !present(position.current)
    ? {
        label: "Average position",
        value: "Unavailable",
        description: gap(position.current),
        trend: null,
        missing: true,
      }
    : {
        label: "Average position",
        value: positionText(position.current.value as number),
        description:
          position.change === null || position.change === undefined
            ? "No earlier month"
            : `${position.change < 0 ? "Moved up" : position.change > 0 ? "Moved down" : "Unchanged"} vs ${monthName(previousOf(month))}`,
        trend: null,
        missing: false,
      };
  return {
    available: true,
    gap: "",
    tiles: [
      comparisonTile("Search clicks", search.clicks, month),
      comparisonTile("Search impressions", search.impressions, month),
      {
        label: "Click-through rate",
        value: rateText(ctr.current, (n) => `${n.toFixed(1)}%`),
        description: "Clicks per impression",
        trend: null,
        missing: !present(ctr.current),
      },
      positionTile,
    ],
    queries: search.top_queries.map((row) => searchRow(row.query, row)),
    pages: search.top_pages.map((row) => searchRow(pageLabel(row.page), row)),
    partialNote:
      search.lag_days != null
        ? `Google is still finalizing the last ${search.lag_days} ${search.lag_days === 1 ? "day" : "days"} of the month.`
        : null,
  };
}
/** A page address without its scheme and host: "/menu/", or "Home page". */
export function pageLabel(url: string): string {
  try {
    const { pathname } = new URL(url);
    return pathname === "/" ? "Home page" : pathname;
  } catch {
    return url;
  }
}
export interface AnalyticsView {
  tile: Tile;
}
export function analyticsView(snapshot: ReportSnapshot): AnalyticsView {
  const analytics = snapshot.analytics;
  return {
    tile: comparisonTile(
      "Organic website visits",
      analytics.organic_sessions,
      snapshot.month,
    ),
  };
}
export const WORK_LABEL: Record<WorkKind, string> = {
  gbp_post: "Business Profile posts published",
  website_content: "Website content published",
  review_response: "Review responses published",
  gbp_profile_change: "Business Profile changes applied",
  website_change: "Website changes applied",
};
export interface WorkRow {
  label: string;
  count: string;
  titles: string[];
}
export const workRows = (snapshot: ReportSnapshot): WorkRow[] =>
  snapshot.work.groups.map((group) => ({
    label: WORK_LABEL[group.kind],
    count: fmt(group.count),
    titles: group.titles,
  }));
export const workTotal = (snapshot: ReportSnapshot): number =>
  snapshot.work.groups.reduce((total, group) => total + group.count, 0);
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
const NOTE_TEXT: Record<NoteCode, (note: ReportNote) => string> = {
  gbp_not_connected: () =>
    "Google Business Profile is not connected, so this report has no profile data.",
  gbp_month_not_synced: () =>
    "No day of this month has been synced from Google Business Profile yet.",
  gbp_month_partial: (note) =>
    note.count
      ? `${note.count} ${note.count === 1 ? "day" : "days"} of this month ${note.count === 1 ? "has" : "have"} not synced from Google yet, so profile totals cover part of the month.`
      : "Part of this month has not synced from Google yet, so profile totals cover part of the month.",
  gbp_sync_failed: () =>
    "The last Business Profile sync did not finish, so some days may be missing.",
  gbp_location_not_mapped: () =>
    "A location is not connected to a Business Profile, so it is not in these totals.",
  gbp_search_terms_unavailable: () =>
    "Google has not published this month’s search terms yet.",
  gbp_previous_month_incomplete: () =>
    "The month before is not fully synced, so changes against it are not shown.",
  gbp_year_ago_unavailable: () =>
    "The same month last year is not fully synced, so the yearly comparison is not shown.",
  reviews_not_synced: () =>
    "Reviews have not been synced yet, so review figures are not shown.",
  search_console_not_connected: () =>
    "Search Console is not connected, so search clicks and queries are not shown.",
  search_console_not_synced: () =>
    "Search Console has not delivered this month yet.",
  search_console_lag_days: (note) =>
    note.count
      ? `Google is still finalizing the last ${note.count} ${note.count === 1 ? "day" : "days"} of search data, so those figures may rise.`
      : "Google is still finalizing the last days of search data, so those figures may rise.",
  search_console_previous_month_unavailable: () =>
    "Search Console data for the month before is not final, so changes are not shown.",
  analytics_not_connected: () =>
    "Google Analytics is not connected, so website visits are not shown.",
  analytics_not_synced: () =>
    "Google Analytics has not delivered this month yet.",
  analytics_organic_unavailable: () =>
    "Google Analytics cannot report search visits for this website.",
  analytics_previous_month_unavailable: () =>
    "Analytics data for the month before is not available, so changes are not shown.",
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
    "The draft mentioned a number that is not in this month’s data, so it was not used.",
  authorship_mentioned: "The draft mentioned who wrote it, so it was not used.",
  causal_claim:
    "The draft claimed one thing caused another, which the data cannot show, so it was not used.",
};
const FAILURES: Record<string, string> = {
  REPORT_NARRATIVE_EMPTY: "Write both narrative sections before approving.",
  REPORT_DATA_MISSING:
    "This report is missing the Business Profile data it needs. Reconnect Google, then generate it again.",
  REPORT_NOT_EDITABLE: "An approved report cannot be edited.",
  REPORT_REVISION_SUPERSEDED:
    "A newer version of this report exists. Reload to see it.",
  REPORT_ALREADY_APPROVED:
    "This report is already approved and the data has not changed.",
  REPORT_NOT_APPROVED: "Approve the report before recording it as sent.",
  REPORT_SENT_DATE_INVALID:
    "Choose a day after the month ended and not in the future.",
  REPORT_MONTH_NOT_ENDED: "A report covers a month that has ended.",
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
  sections: { title: string; paragraphs: string[]; field: string }[];
  empty: boolean;
  drafted: boolean;
}
const paragraphs = (text: string) =>
  text
    .split(/\n{2,}/)
    .map((part) => part.trim())
    .filter(Boolean);
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
              ? "Business Profile data is missing for this month."
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
export const headline = (report: ReportDetail) =>
  `${monthLabel(report.month)} performance report`;
export interface Confirm {
  title: string;
  lines: string[];
  accept: string;
}
/** The exact period and client an approval or a send applies to. */
export function approveCopy(client: string, month: string): Confirm {
  return {
    title: "Approve this report?",
    lines: [
      `${client} · ${monthLabel(month)} (${monthRange(month)}).`,
      "Once approved, its numbers and wording are locked. If the data changes later, a new draft is made and this one stays as approved.",
      "Approving does not send anything to the client.",
    ],
    accept: "Approve report",
  };
}
export function sendCopy(
  client: string,
  month: string,
  sentOn: string,
): Confirm {
  return {
    title: "Record this report as sent?",
    lines: [
      `${client} · ${monthLabel(month)} (${monthRange(month)}).`,
      `You are recording that you sent it to the client on ${dateText(sentOn)}. LILOs does not email the report.`,
    ],
    accept: "Record as sent",
  };
}
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
          ? MISSING
          : "Not sent yet",
      href: row.status
        ? reportHref(row.slug, row.month)
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
  version: string | null;
  status: Chip;
  readiness: Chip;
  delivered: string;
  href: string;
  current: boolean;
}
/** Every stored revision, newest month first. A month with several shows which version it is. */
export function historyRows(list: ReportList, slug: string): HistoryRowView[] {
  const perMonth = new Map<string, number>();
  for (const row of list.history)
    perMonth.set(row.month, (perMonth.get(row.month) ?? 0) + 1);
  return list.history.map((row: ReportRevisionRow) => ({
    period: monthLabel(row.month),
    version:
      (perMonth.get(row.month) ?? 0) > 1 ? `Version ${row.revision}` : null,
    status: reportChip(row.status),
    readiness: readinessChip(row.readiness),
    delivered: row.delivery ? dateText(row.delivery.sent_on) : MISSING,
    href: summaryHref(slug, row.month, row.revision),
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
      href: reportHref(slug, current.month),
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
