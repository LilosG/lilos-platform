/**
 * The client document: what the report says, section by section, as plain data for the page to
 * draw. Every figure comes from the stored snapshot; nothing is recomputed here and nothing that
 * is missing is shown as a number. A figure the report cannot state is left out of its table or
 * chart and named under "Not included in this report".
 */
import type {
  CountComparison,
  RateComparison,
  ReportDetail,
  ReportSnapshot,
  SeriesKey,
} from "../adapters/reports";
import {
  barChart,
  horizontalBars,
  type BarChartModel,
  type BarInput,
  type HorizontalModel,
} from "./report-charts";
import {
  changeText,
  comparedLabel,
  comparedPhrase,
  countText,
  directionOf,
  gapText,
  headlineCards,
  isPartial,
  metricLabel,
  monthLabel,
  monthShort,
  narrativeParagraphs,
  noteText,
  percentText,
  periodLabel,
  periodOf,
  present,
  ratingText,
  rateText,
  toneOf,
  type Better,
  type HeadlineCard,
  type Tone,
} from "./report-view";
import { DISPLAY_TIME_ZONE, dateText, fmt, positionText } from "./present";
import { monthsOf } from "./report-period";

const longDay = (iso: string) =>
  new Intl.DateTimeFormat("en-US", {
    timeZone: DISPLAY_TIME_ZONE,
    month: "long",
    day: "numeric",
    year: "numeric",
  }).format(new Date(iso));
const plural = (count: number, one: string, many: string) =>
  `${fmt(count)} ${count === 1 ? one : many}`;

export type Direction = "up" | "down" | "flat" | "none";
export interface ScoreRow {
  label: string;
  current: string;
  compared: string;
  change: string;
  direction: Direction;
  tone: Tone;
  /** The same period a year earlier, with its change; null when this row has none to show. */
  year: string | null;
  partial: boolean;
}
export interface ScoreGroup {
  id: "gbp" | "search" | "traffic" | "reviews";
  title: string;
  rows: ScoreRow[];
}
export interface Scorecard {
  groups: ScoreGroup[];
  /** Whether the "same period last year" column is drawn: only when some row has it. */
  hasYear: boolean;
  /** Notes that explain a row, such as a figure Google stopped reporting. */
  rowNotes: string[];
  footnotes: string[];
}
const PARTIAL_FOOTNOTE: Record<ScoreGroup["id"], string> = {
  gbp: "* Business Profile figures cover only part of the period; some days have not synced yet.",
  search:
    "* Search figures cover only the months Google has delivered so far, or a month Google has not finished.",
  traffic:
    "* Website visit figures cover only the months synced so far, or a month not yet final.",
  reviews: "",
};
function countCells(comparison: CountComparison) {
  const averaged = comparison.compared_as === "monthly_average";
  const current = countText(comparison.current) ?? "";
  const compared = countText(comparison.compared);
  return {
    current:
      averaged && comparison.current_monthly_average != null
        ? `${current} (${fmt(comparison.current_monthly_average)} a month)`
        : current,
    compared: compared
      ? averaged
        ? `${compared} a month`
        : compared
      : gapText(comparison.compared),
  };
}
function yearCell(comparison: CountComparison): string | null {
  const year = comparison.year_ago;
  if (year === null || year === undefined) return null;
  const value = countText(year);
  if (!value) return gapText(year);
  const change = changeText(comparison, "year");
  return change ? `${value} (${change})` : value;
}
function countRow(label: string, comparison: CountComparison): ScoreRow | null {
  if (!present(comparison.current)) return null;
  const { current, compared } = countCells(comparison);
  const change = changeText(comparison);
  const partial =
    isPartial(comparison.current) || isPartial(comparison.compared);
  return {
    label,
    current,
    compared,
    change: change ?? (partial ? "Not comparable" : "No comparison"),
    direction: directionOf(comparison.change),
    tone: toneOf(directionOf(comparison.change)),
    year: yearCell(comparison),
    partial: isPartial(comparison.current),
  };
}
function rateRow(
  label: string,
  comparison: RateComparison,
  format: (value: number) => string,
  unit: string,
  better: Better = "higher",
): ScoreRow | null {
  if (!present(comparison.current)) return null;
  const point = (change: number | null | undefined) =>
    change === null || change === undefined
      ? null
      : `${change > 0 ? "+" : change < 0 ? "−" : ""}${Math.abs(change).toFixed(1)} ${unit}`;
  const partial =
    isPartial(comparison.current) || isPartial(comparison.compared);
  const year = comparison.year_ago;
  return {
    label,
    current: rateText(comparison.current, format) ?? "",
    compared:
      rateText(comparison.compared, format) ?? gapText(comparison.compared),
    change:
      point(comparison.change) ??
      (partial ? "Not comparable" : "No comparison"),
    direction: directionOf(comparison.change),
    tone: toneOf(directionOf(comparison.change), better),
    year:
      year === null || year === undefined
        ? null
        : present(year)
          ? `${rateText(year, format)}${point(comparison.year_change) ? ` (${point(comparison.year_change)})` : ""}`
          : gapText(year),
    partial: isPartial(comparison.current),
  };
}
const keep = (rows: (ScoreRow | null)[]): ScoreRow[] =>
  rows.filter((row): row is ScoreRow => row !== null);
export function scorecard(snapshot: ReportSnapshot): Scorecard {
  const { gbp, search_console: search, analytics, reviews } = snapshot;
  const rowNotes: string[] = [];
  const groups: ScoreGroup[] = [];
  if (gbp.availability !== "unavailable") {
    const optional = gbp.actions.optional.flatMap((row): ScoreRow[] => {
      const label = metricLabel(row.metric);
      if (row.comparable) {
        const made = countRow(label, row.comparison);
        return made ? [made] : [];
      }
      // Google reported none this period but some before: not a result, and not a change.
      const note = snapshot.notes.find(
        (item) =>
          item.code === "optional_figure_not_reported" &&
          item.metric === row.metric,
      );
      if (note) rowNotes.push(noteText(note));
      return [
        {
          label,
          current: "Not reported",
          compared:
            countText(row.comparison.compared) ??
            gapText(row.comparison.compared),
          change: "Not comparable",
          direction: "none",
          tone: "neutral",
          year: null,
          partial: false,
        },
      ];
    });
    groups.push({
      id: "gbp",
      title: "Google Business Profile",
      rows: keep([
        countRow("Profile views", gbp.profile_views.total),
        countRow("Profile actions", gbp.actions.total),
        ...gbp.actions.actions
          .filter((row) => row.reported)
          .map((row) => countRow(metricLabel(row.metric), row.comparison)),
        ...optional,
        rateRow(
          "Actions per profile view",
          gbp.actions.action_rate,
          percentText,
          "pts",
        ),
      ]),
    });
  }
  if (search.availability !== "unavailable")
    groups.push({
      id: "search",
      title: "Website search",
      rows: keep([
        countRow("Search clicks", search.clicks),
        countRow("Search impressions", search.impressions),
        rateRow("Click-through rate", search.ctr_percent, percentText, "pts"),
        rateRow(
          "Average position (lower is better)",
          search.average_position,
          positionText,
          "places",
          "lower",
        ),
      ]),
    });
  if (analytics.availability !== "unavailable")
    groups.push({
      id: "traffic",
      title: "Website traffic",
      rows: keep([countRow("Visits from search", analytics.organic_sessions)]),
    });
  if (reviews.availability !== "unavailable")
    groups.push({
      id: "reviews",
      title: "Reviews",
      rows: keep([
        countRow("New reviews", reviews.new_reviews),
        rateRow(
          "Average rating (all reviews)",
          reviews.average_rating_overall,
          ratingText,
          "stars",
        ),
        rateRow(
          "Share of new reviews answered",
          reviews.response_rate_percent,
          (value) => `${Math.round(value)}%`,
          "pts",
        ),
      ]),
    });
  const shown = groups.filter((group) => group.rows.length);
  return {
    groups: shown,
    hasYear: shown.some((group) => group.rows.some((row) => row.year !== null)),
    rowNotes,
    footnotes: shown
      .filter((group) => group.rows.some((row) => row.partial))
      .map((group) => PARTIAL_FOOTNOTE[group.id])
      .filter(Boolean),
  };
}

export interface MonthlyChart {
  title: string;
  model: BarChartModel;
}
function barsOf(snapshot: ReportSnapshot, key: SeriesKey): BarInput[] | null {
  const series = snapshot.monthly.find((item) => item.key === key);
  if (!series) return null;
  const points = [
    ...series.compared.map((point) => ({ point, group: "compared" as const })),
    ...series.period.map((point) => ({ point, group: "period" as const })),
  ];
  let year = "";
  return points.map(({ point, group }) => {
    const shown = point.month.slice(0, 4);
    const label = shown === year ? null : shown;
    year = shown;
    return {
      label: monthShort(point.month),
      year: label,
      value:
        point.availability === "unavailable" ? null : (point.value ?? null),
      partial: point.availability === "partial",
      group,
    };
  });
}
/** The monthly bars for one figure, with the comparison's monthly average as a dashed line. */
export function monthlyChart(
  snapshot: ReportSnapshot,
  key: SeriesKey,
  title: string,
): MonthlyChart | null {
  const bars = barsOf(snapshot, key);
  const series = snapshot.monthly.find((item) => item.key === key);
  if (!bars || !series) return null;
  if (!series.period.some((point) => point.availability !== "unavailable"))
    return null;
  // Only settled months count towards the average a person compares against.
  const settled = series.compared.flatMap((point) =>
    point.availability === "available" &&
    point.value !== null &&
    point.value !== undefined
      ? [point.value]
      : [],
  );
  const average = settled.length
    ? settled.reduce((total, value) => total + value, 0) / settled.length
    : null;
  return {
    title,
    model: barChart({
      title,
      bars,
      baseline: average,
      baselineText:
        average === null
          ? ""
          : `Comparison average: ${fmt(average)} a month (${comparedLabel(snapshot)})`,
      format: fmt,
    }),
  };
}

export interface SplitView {
  title: string;
  model: HorizontalModel;
}
const SPLIT_LABEL = {
  maps: "Google Maps",
  search: "Google Search",
  desktop: "Desktop",
  mobile: "Mobile",
} as const;
/** Maps and Search, desktop and mobile. A split is drawn only when every part is known. */
export function splitViews(snapshot: ReportSnapshot): SplitView[] {
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
          model: horizontalBars(
            title,
            split.parts.map((part) => ({
              label: SPLIT_LABEL[part.key],
              value: part.figure.value as number,
              valueLabel: fmt(part.figure.value as number),
              share: Math.round(part.share_percent as number),
            })),
          ),
        }
      : null;
  };
  return [
    build("Where people found you", snapshot.gbp.profile_views.maps_search),
    build("Device people used", snapshot.gbp.profile_views.desktop_mobile),
  ].filter((item): item is SplitView => item !== null);
}

export interface TermRow {
  keyword: string;
  value: string;
}
export interface TermsView {
  rows: TermRow[];
  /** "and 87 more": the terms beyond those shown. */
  more: number;
  note: string | null;
}
const TOP = 10;
/** Google reports only "fewer than N" for rare searches; that is "< N", never 0. */
function termValue(
  term: ReportSnapshot["gbp"]["search_terms"]["terms"][number],
) {
  if (term.value === null)
    return term.below_threshold === null
      ? null
      : `< ${fmt(term.below_threshold)}`;
  return term.below_threshold === null
    ? fmt(term.value)
    : `${fmt(term.value)}+`;
}
export function termsView(snapshot: ReportSnapshot): TermsView | null {
  const terms = snapshot.gbp.search_terms;
  if (terms.availability === "unavailable" || !terms.terms.length) return null;
  const rows = terms.terms.flatMap((term): TermRow[] => {
    const value = termValue(term);
    return value ? [{ keyword: term.keyword, value }] : [];
  });
  const shown = rows.slice(0, TOP);
  return {
    rows: shown,
    more: Math.max(0, terms.total_terms - shown.length),
    note:
      terms.availability === "partial" &&
      terms.months_covered != null &&
      terms.months_expected != null
        ? `Search terms cover ${terms.months_covered} of ${terms.months_expected} months; Google has not published the rest.`
        : null,
  };
}

export interface ActionsTable {
  months: string[];
  rows: { label: string; cells: string[]; total: string }[];
}
/** Calls, website clicks and directions month by month. A month not synced says so in words. */
export function actionsByMonth(snapshot: ReportSnapshot): ActionsTable | null {
  const find = (key: SeriesKey) =>
    snapshot.monthly.find((item) => item.key === key);
  const lines: [string, SeriesKey, CountComparison | null][] = [
    [
      "Calls",
      "calls",
      snapshot.gbp.actions.actions.find((r) => r.metric === "CALL_CLICKS")
        ?.comparison ?? null,
    ],
    [
      "Website clicks",
      "website_clicks",
      snapshot.gbp.actions.actions.find((r) => r.metric === "WEBSITE_CLICKS")
        ?.comparison ?? null,
    ],
    [
      "Direction requests",
      "direction_requests",
      snapshot.gbp.actions.actions.find(
        (r) => r.metric === "BUSINESS_DIRECTION_REQUESTS",
      )?.comparison ?? null,
    ],
    ["All actions", "profile_actions", snapshot.gbp.actions.total],
  ];
  const rows = lines.flatMap(([label, key, total]) => {
    const series = find(key);
    if (
      !series ||
      !series.period.some((point) => point.availability !== "unavailable")
    )
      return [];
    return [
      {
        label,
        cells: series.period.map((point) =>
          point.availability === "unavailable"
            ? "Not synced"
            : `${fmt(point.value as number)}${point.availability === "partial" ? "*" : ""}`,
        ),
        total: total
          ? (countText(total.current) ?? "Not available")
          : "Not available",
      },
    ];
  });
  if (!rows.length) return null;
  return {
    months: monthsOf(periodOf(snapshot.period)).map((month) =>
      monthShort(month),
    ),
    rows,
  };
}

export interface LocationLine {
  name: string;
  views: string;
  calls: string;
  website: string;
  directions: string;
}
export const locationLines = (snapshot: ReportSnapshot): LocationLine[] =>
  snapshot.gbp.locations.map((row) => ({
    name: row.name,
    views: row.mapped
      ? (countText(row.profile_views.current) ??
        gapText(row.profile_views.current))
      : "Not connected",
    calls: row.mapped
      ? (countText(row.calls.current) ?? gapText(row.calls.current))
      : "Not connected",
    website: row.mapped
      ? (countText(row.website_clicks.current) ??
        gapText(row.website_clicks.current))
      : "Not connected",
    directions: row.mapped
      ? (countText(row.direction_requests.current) ??
        gapText(row.direction_requests.current))
      : "Not connected",
  }));

export interface SearchLine {
  label: string;
  position: string;
  impressions: string;
  clicks: string;
  change: string;
}
type SearchRowLike = Omit<
  ReportSnapshot["search_console"]["top_pages"][number],
  "page"
>;
const rowChange = (row: SearchRowLike, averaged: boolean) =>
  row.clicks_change === null || row.clicks_change === undefined
    ? "No comparison"
    : `${row.clicks_change > 0 ? "+" : row.clicks_change < 0 ? "−" : ""}${fmt(Math.abs(row.clicks_change))}${averaged ? " a month" : ""}`;
/** A page address without its scheme and host: "/menu/", or "Home page". */
export function pageLabel(url: string): string {
  try {
    const { pathname } = new URL(url);
    return pathname === "/" ? "Home page" : pathname;
  } catch {
    return url;
  }
}
export interface SearchView {
  queries: SearchLine[];
  brandedNote: string | null;
  pages: SearchLine[];
  topNote: string;
  lagNote: string | null;
}
export function searchView(
  snapshot: ReportSnapshot,
  client: string,
): SearchView | null {
  const search = snapshot.search_console;
  if (search.availability === "unavailable") return null;
  const averaged = snapshot.comparison.compared_as === "monthly_average";
  const line = (label: string, row: SearchRowLike): SearchLine => ({
    label,
    position:
      row.position === null ? "Not available" : positionText(row.position),
    impressions: fmt(row.impressions),
    clicks: fmt(row.clicks),
    change: rowChange(row, averaged),
  });
  const share = search.branded_share_percent;
  return {
    queries: search.top_queries
      .filter((row) => !row.is_branded)
      .slice(0, TOP)
      .map((row) => line(row.query, row)),
    brandedNote:
      share === null || share === undefined
        ? null
        : `Searches that name ${client} made up ${Math.round(share)}% of the clicks from the top searches. They are left out of this list.`,
    pages: search.top_pages
      .slice(0, TOP)
      .map((row) => line(pageLabel(row.page), row)),
    topNote:
      "Top searches and pages are added up from the highest-ranking ones Google reports each month. They are not totals of every search.",
    lagNote:
      search.lag_days != null
        ? `Google is still finalizing the last ${plural(search.lag_days, "day", "days")} of search data, so these figures may rise.`
        : null,
  };
}

export interface ReviewsView {
  rating: string | null;
  total: string | null;
  stats: { label: string; value: string; detail: string }[];
  distribution: HorizontalModel | null;
}
export function reviewsView(snapshot: ReportSnapshot): ReviewsView | null {
  const reviews = snapshot.reviews;
  if (reviews.availability === "unavailable") return null;
  const total = reviews.distribution_overall.reduce(
    (n, row) => n + row.count,
    0,
  );
  const rows = [...reviews.distribution_overall]
    .sort((a, b) => b.stars - a.stars)
    .map((row) => ({
      label: `${row.stars} ${row.stars === 1 ? "star" : "stars"}`,
      value: row.count,
      valueLabel: plural(row.count, "review", "reviews"),
      share: total ? Math.round((row.count / total) * 100) : 0,
    }));
  const against = comparedPhrase({
    compared_as: reviews.new_reviews.compared_as,
    compared: periodOf(snapshot.comparison.compared),
  });
  const newCount = countText(reviews.new_reviews.current);
  const change = changeText(reviews.new_reviews);
  const answered = rateText(
    reviews.response_rate_percent.current,
    (v) => `${Math.round(v)}%`,
  );
  const published = countText(reviews.responses_published);
  const inPeriod = rateText(
    reviews.average_rating_in_period.current,
    ratingText,
  );
  return {
    rating: rateText(reviews.average_rating_overall.current, ratingText),
    total: countText(reviews.total_count),
    stats: [
      ...(newCount
        ? [
            {
              label: "New reviews",
              value: newCount,
              detail: change
                ? `${change} vs ${against}`
                : "Written in this period",
            },
          ]
        : []),
      ...(inPeriod
        ? [
            {
              label: "Rating of new reviews",
              value: inPeriod,
              detail: "Average of reviews written in this period",
            },
          ]
        : []),
      ...(answered
        ? [
            {
              label: "Response rate",
              value: answered,
              detail: "Of this period’s new reviews",
            },
          ]
        : []),
      ...(published
        ? [
            {
              label: "Replies published",
              value: published,
              detail: "Posted during this period",
            },
          ]
        : []),
    ],
    distribution: total
      ? horizontalBars("Star ratings across all reviews", rows)
      : null,
  };
}

export interface WorkLine {
  label: string;
  count: string;
  titles: string[];
}
const WORK_LABEL = {
  gbp_post: "Business Profile posts published",
  website_content: "Website content published",
  review_response: "Review responses published",
  gbp_profile_change: "Business Profile changes applied",
  website_change: "Website changes applied",
} as const;
/** Work that was finished in the period. A kind with none is left out, not listed as 0. */
export const workLines = (snapshot: ReportSnapshot): WorkLine[] =>
  snapshot.work.groups
    .filter((group) => group.count > 0)
    .map((group) => ({
      label: WORK_LABEL[group.kind],
      count: fmt(group.count),
      titles: group.titles,
    }));

/** The figures this report could not state, each with the reason, for "Not included". */
export function notIncluded(snapshot: ReportSnapshot): string[] {
  const out: string[] = [];
  const { gbp, search_console: search, analytics, reviews } = snapshot;
  if (snapshot.local_rank.state === "not_tracked")
    out.push("Local search ranking: not tracked yet");
  if (gbp.availability === "unavailable")
    out.push(
      `Google Business Profile views and actions: ${gbp.reason ? gapText({ reason: gbp.reason } as never).toLowerCase() : "not available"}`,
    );
  else {
    if (gbp.search_terms.availability === "unavailable")
      out.push(
        `Google Business Profile search terms: ${gapText(gbp.search_terms as never).toLowerCase()}`,
      );
    if (!present(gbp.actions.action_rate.current))
      out.push("Actions per profile view: not available");
  }
  if (search.availability === "unavailable")
    out.push(
      `Website search from Search Console: ${gapText(search as never).toLowerCase()}`,
    );
  else {
    if (!present(search.ctr_percent.current))
      out.push("Click-through rate: not available");
    if (!present(search.average_position.current))
      out.push("Average position: not available");
  }
  if (analytics.availability === "unavailable")
    out.push(
      `Website visits from Google Analytics: ${gapText(analytics as never).toLowerCase()}`,
    );
  if (reviews.availability === "unavailable")
    out.push(`Reviews: ${gapText(reviews as never).toLowerCase()}`);
  const sources: [SeriesKey, string, boolean][] = [
    [
      "profile_views",
      "Business Profile figures",
      gbp.availability !== "unavailable",
    ],
    [
      "search_clicks",
      "Website search figures",
      search.availability !== "unavailable",
    ],
    [
      "organic_sessions",
      "Website visits",
      analytics.availability !== "unavailable",
    ],
  ];
  for (const [key, label, section] of sources) {
    const series = snapshot.monthly.find((item) => item.key === key);
    const missing = (series?.period ?? []).filter(
      (p) => p.availability === "unavailable",
    );
    if (section && missing.length)
      out.push(
        `${label} for ${missing.map((p) => monthLabel(p.month)).join(", ")}: not synced yet`,
      );
  }
  const card = scorecard(snapshot);
  if (snapshot.comparison.year_ago && card.groups.length && !card.hasYear)
    out.push("Comparison with the same months last year: not available");
  return out;
}

export interface Definition {
  term: string;
  text: string;
}
/** What each figure is and where it comes from, for the figures this report contains. */
export function definitions(
  snapshot: ReportSnapshot,
  client: string,
): Definition[] {
  const list: Definition[] = [];
  const has = (group: ScoreGroup["id"]) =>
    scorecard(snapshot).groups.some((item) => item.id === group);
  if (has("gbp"))
    list.push(
      {
        term: "Profile views",
        text: "Times your Business Profile appeared in Google Search and Google Maps, on desktop and mobile. Source: Google Business Profile.",
      },
      {
        term: "Profile actions",
        text: "Calls, website clicks and direction requests made from your Business Profile. Source: Google Business Profile.",
      },
      {
        term: "Search terms",
        text: "What people searched for before they saw your profile. Google reports a count for common terms and only “fewer than” a number for rare ones, which are shown as “< N”. Source: Google Business Profile.",
      },
    );
  if (has("search"))
    list.push(
      {
        term: "Search clicks, impressions and click-through rate",
        text: "Clicks to your website from Google Search, how often your pages appeared, and clicks as a share of appearances. Source: Google Search Console.",
      },
      {
        term: "Average position",
        text: "Where your pages ranked in Google Search on average, weighted by how often each appeared. Lower is better. Source: Google Search Console.",
      },
      {
        term: "Top searches and top pages",
        text: "Added up from the highest-ranking searches and pages Google reports for each month. They show what mattered most; they are not totals of every search.",
      },
      {
        term: "Branded searches",
        text: `A search is branded when, ignoring capital letters, apostrophes and punctuation, it contains the name of the business (${client}) or one of its locations. Branded searches are left out of the list of top searches.`,
      },
    );
  if (has("traffic"))
    list.push({
      term: "Visits from search",
      text: "Website visits that began with an unpaid Google search. Source: Google Analytics.",
    });
  if (has("reviews"))
    list.push({
      term: "Reviews",
      text: "Counted from your Google reviews. Reviews Google no longer lists are not counted. Average rating covers all reviews up to the end of the period.",
    });
  const { gbp, comparison, period } = snapshot;
  if (comparison.compared_as === "monthly_average")
    list.push({
      term: "Compared as monthly averages",
      text: `This report covers ${plural(monthsOf(periodOf(period)).length, "month", "months")} and the comparison covers ${plural(monthsOf(periodOf(comparison.compared)).length, "month", "months")}, so counts are compared as monthly averages. Rates and positions are compared directly.`,
    });
  if (gbp.current_range.days !== gbp.compared_range.days)
    list.push({
      term: "Business Profile days compared",
      text: `Business Profile figures cover ${plural(gbp.current_range.days, "day", "days")} this period and ${plural(gbp.compared_range.days, "day", "days")} in the comparison.`,
    });
  return list;
}

export interface CoverView {
  client: string;
  title: string;
  period: string;
  range: string;
  compared: string;
  locations: string[];
  preparedBy: string;
  preparedOn: string;
}
export interface DocumentView {
  cover: CoverView;
  headlines: HeadlineCard[];
  whatChanged: string[];
  scorecard: Scorecard;
  gbp: {
    charts: MonthlyChart[];
    splits: SplitView[];
    terms: TermsView | null;
    actions: ActionsTable | null;
    locations: LocationLine[];
  } | null;
  search: {
    charts: MonthlyChart[];
    view: SearchView;
  } | null;
  reviews: ReviewsView | null;
  work: WorkLine[];
  nextWork: string[];
  notes: {
    definitions: Definition[];
    dataNotes: string[];
    footnotes: string[];
    sync: string[];
    notIncluded: string[];
    period: string;
  };
}
/** The whole client document for one stored revision. */
export function documentView(report: ReportDetail): DocumentView {
  const snapshot = report.snapshot;
  const period = periodOf(snapshot.period);
  const card = scorecard(snapshot);
  const charts = (specs: [SeriesKey, string][]): MonthlyChart[] =>
    specs.flatMap(([key, title]) => {
      const chart = monthlyChart(snapshot, key, title);
      return chart ? [chart] : [];
    });
  const search = searchView(snapshot, report.client_name);
  const sync: string[] = [];
  const when = (iso: string | null | undefined, source: string) =>
    iso ? sync.push(`${source} last synced ${dateText(iso)}.`) : undefined;
  when(snapshot.sync.gbp, "Google Business Profile");
  when(snapshot.sync.search_console, "Search Console");
  when(snapshot.sync.analytics, "Google Analytics");
  const gbpShown = snapshot.gbp.availability !== "unavailable";
  return {
    cover: {
      client: report.client_name,
      title: "Performance report",
      period: periodLabel(period),
      range: periodLabelRange(report),
      compared: `Compared with: ${comparedText(snapshot)}`,
      locations: snapshot.location_names,
      preparedBy: "Lilos Growth",
      preparedOn: longDay(report.approved_at ?? report.created_at),
    },
    headlines: headlineCards(snapshot),
    whatChanged: narrativeParagraphs(report.narrative.what_changed),
    scorecard: card,
    gbp: gbpShown
      ? {
          charts: charts([
            ["profile_views", "Profile views by month"],
            ["profile_actions", "Profile actions by month"],
          ]),
          splits: splitViews(snapshot),
          terms: termsView(snapshot),
          actions: actionsByMonth(snapshot),
          locations: locationLines(snapshot),
        }
      : null,
    search: search
      ? {
          charts: charts([
            ["search_clicks", "Search clicks by month"],
            ["search_impressions", "Search impressions by month"],
          ]),
          view: search,
        }
      : null,
    reviews: reviewsView(snapshot),
    work: workLines(snapshot),
    nextWork: narrativeParagraphs(report.narrative.next_work),
    notes: {
      definitions: definitions(snapshot, report.client_name),
      dataNotes: snapshot.notes.map(noteText),
      footnotes: card.footnotes,
      sync,
      notIncluded: notIncluded(snapshot),
      period: `${periodLabel(period)} (${periodLabelRange(report)}). Compared with ${comparedText(snapshot)}.`,
    },
  };
}
const periodLabelRange = (report: ReportDetail) => rangeOf(report.snapshot);
function rangeOf(snapshot: ReportSnapshot) {
  const { start, end } = snapshot.gbp.current_range;
  return `${dateText(start)} – ${dateText(end)}`;
}
/** The comparison in words for the cover: "February – April 2026" or "the same months last year". */
function comparedText(snapshot: ReportSnapshot): string {
  const label = comparedLabel(snapshot);
  const { basis, compared_as: as } = snapshot.comparison;
  if (basis === "same_period_last_year")
    return `the same period last year (${label})`;
  if (basis === "custom_baseline")
    return `${label}${as === "monthly_average" ? ", as monthly averages" : ""}`;
  return label;
}
