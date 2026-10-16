/**
 * The client document: what the report says, section by section, as plain data for the page to
 * draw. Every figure comes from the stored snapshot; nothing is recomputed here and nothing that
 * is missing is shown as a number. A figure the report cannot state is left out of its table or
 * chart and named under "Not included in this report".
 */
import type {
  CountComparison,
  FigureKey,
  RateComparison,
  ReportDetail,
  ReportSnapshot,
  ResultCard,
  SearchResults,
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
  comparisonText,
  countText,
  directionOf,
  gapText,
  isPartial,
  metricLabel,
  monthLabel,
  monthName,
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
  type Tone,
} from "./report-view";
import { DISPLAY_TIME_ZONE, dateText, fmt, signed } from "./present";
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
const SOURCE = {
  gbp: "Google Business Profile",
  search: "Google Search Console",
  traffic: "Google Analytics",
  reviews: "Google reviews",
} as const;
export interface ScoreRow {
  label: string;
  /** Where the figure comes from, under the label. */
  source: string;
  /** Why a figure reads the way it does, when it would otherwise be bare. */
  note: string | null;
  current: string;
  /** A second line under the figure, such as "1,800 a month". */
  currentSub: string | null;
  compared: string;
  change: string;
  direction: Direction;
  tone: Tone;
  /** The same period a year earlier; null when this row has none to show. */
  year: string | null;
  /** Its change, for the muted second line under the value. */
  yearChange: string | null;
  partial: boolean;
}
export interface ScoreGroup {
  id: "gbp" | "search" | "traffic" | "reviews";
  title: string;
  /** The small mono line above the group: what it is and what it is compared with. */
  kicker: string;
  rows: ScoreRow[];
}
export interface Scorecard {
  groups: ScoreGroup[];
  /** Whether the "same period last year" column is drawn: only when some row has it. */
  hasYear: boolean;
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
    current,
    currentSub:
      averaged && comparison.current_monthly_average != null
        ? `${fmt(comparison.current_monthly_average)} a month`
        : null,
    compared: compared
      ? averaged
        ? `${compared} a month`
        : compared
      : gapText(comparison.compared),
  };
}
function yearCell(comparison: CountComparison): {
  year: string | null;
  yearChange: string | null;
} {
  const year = comparison.year_ago;
  if (year === null || year === undefined)
    return { year: null, yearChange: null };
  const value = countText(year);
  if (!value) return { year: gapText(year), yearChange: null };
  return { year: value, yearChange: changeText(comparison, "year") };
}
function countRow(
  label: string,
  source: string,
  comparison: CountComparison,
  note: string | null = null,
): ScoreRow | null {
  if (!present(comparison.current)) return null;
  const cells = countCells(comparison);
  const change = changeText(comparison);
  const partial =
    isPartial(comparison.current) || isPartial(comparison.compared);
  return {
    label,
    source,
    note,
    ...cells,
    change: change ?? (partial ? "Not comparable" : "No comparison"),
    direction: directionOf(comparison.change),
    tone: toneOf(directionOf(comparison.change)),
    ...yearCell(comparison),
    partial: isPartial(comparison.current),
  };
}
function rateRow(
  label: string,
  source: string,
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
    source,
    note: null,
    current: rateText(comparison.current, format) ?? "",
    currentSub: null,
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
          ? rateText(year, format)
          : gapText(year),
    yearChange:
      year !== null && year !== undefined && present(year)
        ? point(comparison.year_change)
        : null,
    partial: isPartial(comparison.current),
  };
}
const keep = (rows: (ScoreRow | null)[]): ScoreRow[] =>
  rows.filter((row): row is ScoreRow => row !== null);
/** "+76 searches (+80%)": a count of searches before and after. */
function searchCountRow(
  label: string,
  before: number | null,
  after: number,
): ScoreRow {
  const change = before === null ? null : after - before;
  const percent = before ? ((after - before) / before) * 100 : null;
  const direction = directionOf(change);
  return {
    label,
    source: "Search Console, non-branded searches",
    note: null,
    current: fmt(after),
    currentSub: null,
    compared: before === null ? "No comparison" : fmt(before),
    change:
      change === null
        ? "No comparison"
        : `${change > 0 ? "+" : change < 0 ? "−" : ""}${fmt(Math.abs(change))}${percent === null ? "" : ` (${signed(percent, 0)})`}`,
    direction,
    tone: toneOf(direction),
    year: null,
    yearChange: null,
    partial: false,
  };
}
export function scorecard(
  snapshot: ReportSnapshot,
  results: SearchResults | null = null,
): Scorecard {
  const { gbp, search_console: search, analytics, reviews } = snapshot;
  const groups: ScoreGroup[] = [];
  const versus = `${periodLabel(periodOf(snapshot.period))} vs. ${comparedLabel(snapshot)}${snapshot.comparison.compared_as === "monthly_average" ? ", as monthly averages" : ""}`;
  if (gbp.availability !== "unavailable") {
    const optional = gbp.actions.optional.flatMap((row): ScoreRow[] => {
      const label = metricLabel(row.metric);
      if (row.comparable) {
        const made = countRow(label, SOURCE.gbp, row.comparison);
        return made ? [made] : [];
      }
      // Google reported none this period but some before: not a result, and not a change.
      const note = snapshot.notes.find(
        (item) =>
          item.code === "optional_figure_not_reported" &&
          item.metric === row.metric,
      );
      return [
        {
          label,
          source: SOURCE.gbp,
          note: note ? noteText(note) : null,
          current: "Not reported",
          currentSub: null,
          compared:
            countText(row.comparison.compared) ??
            gapText(row.comparison.compared),
          change: "Not comparable",
          direction: "none",
          tone: "neutral",
          year: null,
          yearChange: null,
          partial: false,
        },
      ];
    });
    groups.push({
      id: "gbp",
      title: "Google Business Profile",
      kicker: `Google Business Profile · ${versus}`,
      rows: keep([
        countRow("Profile views", SOURCE.gbp, gbp.profile_views.total),
        countRow("Profile actions", SOURCE.gbp, gbp.actions.total),
        ...gbp.actions.actions
          .filter((row) => row.reported)
          .map((row) =>
            countRow(metricLabel(row.metric), SOURCE.gbp, row.comparison),
          ),
        ...optional,
        rateRow(
          "Actions per profile view",
          SOURCE.gbp,
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
      title: "Website and Google search",
      kicker: `Website & Google search · ${versus}`,
      rows: keep([
        countRow("Search clicks", SOURCE.search, search.clicks),
        countRow("Search impressions", SOURCE.search, search.impressions),
        rateRow(
          "Click-through rate",
          SOURCE.search,
          search.ctr_percent,
          percentText,
          "pts",
        ),
        rateRow(
          "Average position (lower is better)",
          SOURCE.search,
          search.average_position,
          (value) => value.toFixed(1),
          "places",
          "lower",
        ),
        results
          ? searchCountRow(
              "Non-branded searches in Google’s top 10",
              results.top_ten_before ?? null,
              results.top_ten_after,
            )
          : null,
        results && results.new_to_page_one !== null && results.comparable
          ? {
              ...searchCountRow(
                "Searches new to page one",
                null,
                results.new_to_page_one ?? 0,
              ),
              change: "New",
              direction: "none" as const,
              tone: "neutral" as const,
            }
          : null,
      ]),
    });
  if (analytics.availability !== "unavailable")
    groups.push({
      id: "traffic",
      title: "Website visits",
      kicker: `Website visits · ${versus}`,
      rows: keep([
        countRow(
          "Visits from search",
          SOURCE.traffic,
          analytics.organic_sessions,
        ),
      ]),
    });
  if (reviews.availability !== "unavailable")
    groups.push({
      id: "reviews",
      title: "Reviews",
      kicker: `Reviews · ${versus}`,
      rows: keep([
        countRow("New reviews", SOURCE.reviews, reviews.new_reviews),
        rateRow(
          "Average rating (all reviews)",
          SOURCE.reviews,
          reviews.average_rating_overall,
          ratingText,
          "stars",
        ),
        rateRow(
          "Share of new reviews answered",
          SOURCE.reviews,
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
    footnotes: shown
      .filter((group) => group.rows.some((row) => row.partial))
      .map((group) => PARTIAL_FOOTNOTE[group.id])
      .filter(Boolean),
  };
}

export interface MonthlyChart {
  title: string;
  /** A chart of a few bars, drawn narrow so two sit side by side. */
  compact: boolean;
  /** One line on what to take from the chart. */
  caption: string;
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
/**
 * What to take from a monthly chart, in one line: the period's figure against its comparison.
 * Months with no data are named as blank, never as zero.
 */
export function chartCaption(
  noun: string,
  comparison: CountComparison | null,
  snapshot: ReportSnapshot,
  missing: number,
): string {
  const gap =
    missing > 0
      ? ` ${plural(missing, "month", "months")} without data ${missing === 1 ? "is" : "are"} left blank, not shown as zero.`
      : "";
  if (!comparison || !present(comparison.current))
    return `${noun}.${gap}`.trim();
  const total = countText(comparison.current);
  const averaged = comparison.compared_as === "monthly_average";
  const change = changeText(comparison);
  const against = comparedPhrase({
    compared_as: comparison.compared_as,
    compared: periodOf(snapshot.comparison.compared),
  });
  return `${noun} totalled ${total} in ${periodLabel(periodOf(snapshot.period))}${
    change && !isPartial(comparison.current)
      ? `, ${change} against ${against}${averaged ? " (monthly averages)" : ""}`
      : ""
  }.${gap}`;
}
/** The monthly bars for one figure, with the comparison's monthly average as a dashed line. */
export function monthlyChart(
  snapshot: ReportSnapshot,
  key: SeriesKey,
  title: string,
  comparison: CountComparison | null = null,
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
  const missing = [...series.period, ...series.compared].filter(
    (point) => point.availability === "unavailable",
  ).length;
  const compact = bars.length <= 4;
  return {
    title,
    compact,
    caption: chartCaption(
      title.replace(/ by month$/, ""),
      comparison,
      snapshot,
      missing,
    ),
    model: barChart({
      title,
      bars,
      baseline: average,
      baselineText:
        average === null
          ? ""
          : `Comparison average: ${fmt(average)} a month (${comparedLabel(snapshot)})`,
      format: fmt,
      ...(compact ? { width: 320, height: 210 } : {}),
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

/** A page address without its scheme, host, query or index file: "/menu", or "/" for home. */
export function pagePath(url: string): string {
  let path = url;
  try {
    path = new URL(url).pathname;
  } catch {
    path = url.split(/[?#]/)[0];
  }
  path = path.replace(/\/index(?:\.html?|\.php)?$/i, "/");
  if (path.length > 1) path = path.replace(/\/+$/, "");
  return path || "/";
}
export const pageLabel = (url: string): string => {
  const path = pagePath(url);
  return path === "/" ? "Home page" : path;
};
type PageRow = ReportSnapshot["search_console"]["top_pages"][number];
/** Addresses that are the same page (http and https, www, a trailing slash, index.html) added up. */
export function mergePages(rows: PageRow[]): PageRow[] {
  const merged = new Map<string, PageRow>();
  for (const row of rows) {
    const path = pagePath(row.page);
    const found = merged.get(path);
    if (!found) {
      merged.set(path, { ...row, page: path });
      continue;
    }
    const impressions = found.impressions + row.impressions;
    const weigh = (
      a: number | null,
      ai: number,
      b: number | null,
      bi: number,
    ) =>
      a === null && b === null
        ? null
        : impressions
          ? ((a ?? 0) * ai + (b ?? 0) * bi) / impressions
          : null;
    const clicks = found.clicks + row.clicks;
    const compared =
      found.compared_clicks == null && row.compared_clicks == null
        ? null
        : (found.compared_clicks ?? 0) + (row.compared_clicks ?? 0);
    merged.set(path, {
      page: path,
      clicks,
      impressions,
      ctr: impressions ? (clicks / impressions) * 100 : null,
      position: weigh(
        found.position,
        found.impressions,
        row.position,
        row.impressions,
      ),
      compared_clicks: compared,
      clicks_change:
        found.clicks_change == null && row.clicks_change == null
          ? null
          : (found.clicks_change ?? 0) + (row.clicks_change ?? 0),
    });
  }
  return [...merged.values()].sort(
    (a, b) => b.clicks - a.clicks || b.impressions - a.impressions,
  );
}
export interface PageLine {
  label: string;
  position: string;
  impressions: string;
  clicks: string;
  change: string;
}

/** "#7.5": a position as people read it on the results page. */
const place = (value: number) => `#${value.toFixed(1)}`;
export interface Pair {
  before: string | null;
  after: string;
}
const pair = (before: number | null, after: number): Pair => ({
  before: before === null ? null : fmt(before),
  after: fmt(after),
});
export interface TopicLine {
  label: string;
  examples: string;
  top10: Pair;
  position: { before: string | null; after: string };
  clicks: Pair;
}
export interface GainLine {
  query: string;
  position: Pair;
  impressions: Pair;
  clicks: Pair;
}
export interface Tile {
  label: string;
  value: string;
  line: string | null;
  tone: Tone;
}
export interface SearchView {
  tiles: Tile[];
  topics: TopicLine[];
  gains: { label: string; rows: GainLine[] }[];
  comparable: boolean;
  /** What the topic table shows, in a line under it. */
  topicNote: string;
  gainNote: string | null;
  coverage: string;
  positionNote: string | null;
  charts: MonthlyChart[];
  pages: PageLine[];
  pagesNote: string;
  lagNote: string | null;
}
const delta = (after: number, before: number | null, noun = "") => {
  if (before === null) return null;
  const change = after - before;
  const percent = before
    ? ` (${signed(((after - before) / before) * 100, 0)})`
    : "";
  return `${change > 0 ? "+" : change < 0 ? "−" : ""}${fmt(Math.abs(change))}${noun}${percent}`;
};
const toneOfChange = (after: number, before: number | null): Tone =>
  before === null ? "neutral" : toneOf(directionOf(after - before));
function topicLine(topic: SearchResults["topics"][number]): TopicLine {
  return {
    label: topic.label,
    examples: topic.examples.join(", "),
    top10: pair(topic.top_ten_before ?? null, topic.top_ten_after),
    position: {
      before:
        topic.position_before === null
          ? null
          : place(topic.position_before).slice(1),
      after:
        topic.position_after === null
          ? "—"
          : place(topic.position_after).slice(1),
    },
    clicks: pair(topic.clicks_before ?? null, topic.clicks_after),
  };
}
function gainLine(
  row: SearchResults["gains"][number]["rows"][number],
): GainLine {
  return {
    query: row.query,
    position: {
      before: row.position_before === null ? "New" : place(row.position_before),
      after: place(row.position_after),
    },
    impressions:
      row.impressions_before === null
        ? { before: "New", after: fmt(row.impressions_after) }
        : pair(row.impressions_before, row.impressions_after),
    clicks:
      (row.clicks_before ?? 0) === 0 && row.clicks_after === 0
        ? { before: null, after: "—" }
        : pair(row.clicks_before ?? null, row.clicks_after),
  };
}
const COVERAGE =
  "Added up from the highest-ranking searches Google reports each month, so these are not totals of every search.";
export function searchView(
  snapshot: ReportSnapshot,
  results: SearchResults | null,
  chartList: MonthlyChart[],
): SearchView | null {
  const search = snapshot.search_console;
  if (search.availability === "unavailable") return null;
  const tiles: Tile[] = [];
  if (results) {
    const from = (line: string | null, before: number | null) =>
      line === null || before === null ? null : `${line} from ${fmt(before)}`;
    tiles.push({
      label: "Searches in Google’s top 10",
      value: fmt(results.top_ten_after),
      line: from(
        delta(results.top_ten_after, results.top_ten_before, " searches"),
        results.top_ten_before,
      ),
      tone: toneOfChange(results.top_ten_after, results.top_ten_before),
    });
    if (results.new_to_page_one !== null)
      tiles.push({
        label: "Searches new to page one",
        value: fmt(results.new_to_page_one),
        line: "since the comparison period",
        tone: results.new_to_page_one > 0 ? "good" : "neutral",
      });
    tiles.push(
      {
        label: "Clicks to the website",
        value: fmt(results.clicks_after),
        line: from(
          delta(results.clicks_after, results.clicks_before),
          results.clicks_before,
        ),
        tone: toneOfChange(results.clicks_after, results.clicks_before),
      },
      {
        label: "Times shown in Google results",
        value: fmt(results.impressions_after),
        line: from(
          delta(results.impressions_after, results.impressions_before),
          results.impressions_before,
        ),
        tone: toneOfChange(
          results.impressions_after,
          results.impressions_before,
        ),
      },
    );
  }
  const averaged =
    results?.position_before != null && results.position_after != null;
  const lag = search.lag_days;
  return {
    tiles,
    topics: results?.topics.map(topicLine) ?? [],
    gains:
      results?.gains.map((group) => ({
        label: group.label,
        rows: group.rows.map(gainLine),
      })) ?? [],
    comparable: !!results?.comparable,
    topicNote: `Position is where the site ranked on average; a lower number is higher on the page, and positions 1–10 are page one. Topics can overlap, so a search such as “little italy happy hour” can count in both. ${COVERAGE}`,
    gainNote: results?.comparable
      ? "Impressions are the number of times the site appeared in Google results for that search. A search that is new to the site’s rankings may not have clicks yet; they usually follow as positions keep climbing."
      : null,
    coverage: results
      ? results.comparable
        ? `Google Search Console, non-branded searches only · ${COVERAGE.replace(", so these are not totals of every search.", ".")}`
        : "Google Search Console, non-branded searches only"
      : "Google Search Console",
    positionNote: averaged
      ? `Across all non-branded searches, average position ${(results!.position_after as number) < (results!.position_before as number) ? "improved" : (results!.position_after as number) > (results!.position_before as number) ? "slipped" : "held"} from ${(results!.position_before as number).toFixed(1)} to ${(results!.position_after as number).toFixed(1)}.`
      : null,
    charts: chartList,
    pages: mergePages(search.top_pages)
      .slice(0, TOP)
      .map((row) => ({
        label: row.page === "/" ? "Home page" : row.page,
        position:
          row.position === null ? "Not available" : row.position.toFixed(1),
        impressions: fmt(row.impressions),
        clicks: fmt(row.clicks),
        change:
          row.clicks_change == null
            ? "No comparison"
            : `${row.clicks_change > 0 ? "+" : row.clicks_change < 0 ? "−" : ""}${fmt(Math.abs(row.clicks_change))}${snapshot.comparison.compared_as === "monthly_average" ? " a month" : ""}`,
      })),
    pagesNote: `Pages people landed on from Google Search. Addresses that are the same page, such as with and without a trailing slash or “www”, are added together. ${COVERAGE}`,
    lagNote:
      lag != null
        ? `Google is still finalizing the last ${plural(lag, "day", "days")} of search data, so these figures may rise.`
        : null,
  };
}

export interface ReviewsView {
  rating: string | null;
  total: string | null;
  stats: { label: string; value: string; detail: string }[];
  distribution: HorizontalModel | null;
  caption: string | null;
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
  const best = rows.find(
    (row) => row.value === Math.max(...rows.map((r) => r.value)),
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
      ? horizontalBars("Star ratings across all reviews", rows, 520)
      : null,
    caption:
      total && best
        ? `${best.share}% of all reviews are ${best.label.toLowerCase()}; every review counted is on Google.`
        : null,
  };
}

export interface WorkLine {
  label: string;
  count: string;
  titles: string[];
  /** "and 12 more": the items beyond those named. */
  more: number;
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
      titles: group.titles.slice(0, TOP),
      more: Math.max(0, group.count - Math.min(group.titles.length, TOP)),
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
    if (!snapshot.search_movement)
      out.push("Search topics and gains: no stored searches for this period");
    else if (!snapshot.search_movement.comparable)
      out.push(
        "Search gains and top 10 changes: the comparison months are not all stored, so nothing is set against them",
      );
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
  const groups = scorecard(snapshot).groups;
  const has = (group: ScoreGroup["id"]) =>
    groups.some((item) => item.id === group);
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
        term: "Searches in Google’s top 10",
        text: "Searches that did not name the business, where the site appeared at least 20 times and ranked 10th or better on average. Position is weighted by how often the site appeared each month.",
      },
      {
        term: "Topics and gains",
        text: "The searches are grouped into topics by wording, and each search is in one topic. A search gained ground when it ranks a place or more better than before, or is new to the site’s rankings. Both are added up from the highest-ranking searches Google reports each month, not from every search.",
      },
      {
        term: "Branded searches",
        text: `A search is branded when, ignoring capital letters, apostrophes and punctuation, it contains the name of the business (${client}) or one of its locations. Common misspellings of the name are treated the same way. Branded searches are left out of the search results.`,
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

const PLAIN_DAY = (iso: string) => {
  const [year, month, day] = iso.split("-").map(Number);
  return `${monthName(`${year}-${String(month).padStart(2, "0")}-01`)} ${day}, ${year}`;
};
export interface Milestone {
  date: string;
  label: string;
}
export interface CoverView {
  /** The small mono line over the title: who this is for, and where. */
  kicker: string;
  title: string;
  intro: string;
  preparedBy: string;
  preparedOn: string;
  /** Dated milestones from the client's business facts; null when it has none. */
  milestones: Milestone[] | null;
}
export interface Head {
  kicker: string;
  title: string;
  intro: string;
  measured: string;
  compared: string | null;
}
export interface GlanceCard {
  value: string;
  tone: Tone;
  headline: boolean;
  title: string;
  text: string;
  footer: string;
}
const CARD_SOURCE: Record<FigureKey, string> = {
  profile_views: SOURCE.gbp,
  profile_actions: SOURCE.gbp,
  calls: SOURCE.gbp,
  website_clicks: SOURCE.gbp,
  direction_requests: SOURCE.gbp,
  search_clicks: "Search Console",
  search_impressions: "Search Console",
  organic_sessions: SOURCE.traffic,
  new_reviews: SOURCE.reviews,
  average_rating: SOURCE.reviews,
  searches_in_top_ten: "Search Console",
  new_to_page_one: "Search Console",
};
/** A result card as the page draws it: the big number is the figure's own change, never text. */
export function glanceCard(
  card: ResultCard,
  snapshot: ReportSnapshot,
): GlanceCard {
  const figure = card.figures[0];
  const percent = figure?.change_percent;
  const value = !figure
    ? ""
    : figure.unit === "stars"
      ? figure.current.toFixed(1)
      : percent !== null && percent !== undefined && figure.compared
        ? `${percent > 0 ? "+" : percent < 0 ? "−" : ""}${fmt(Math.abs(percent))}%`
        : fmt(figure.current);
  const period = periodLabel(periodOf(snapshot.period));
  const versus =
    figure && figure.compared != null ? ` vs. ${comparedLabel(snapshot)}` : "";
  return {
    value,
    tone: card.tone,
    headline: card.headline,
    title: card.title,
    text: card.text,
    footer: [
      `${period}${versus}`,
      figure?.monthly_average ? "per month" : null,
      figure ? CARD_SOURCE[figure.key] : null,
    ]
      .filter(Boolean)
      .join(" · "),
  };
}

export interface DocumentView {
  /** A draft prints "Draft - not for sending" and is downloaded as a draft. */
  draft: boolean;
  cover: CoverView;
  glance: {
    head: Head;
    cards: GlanceCard[];
    prose: string[];
  } | null;
  scorecard: { head: Head; card: Scorecard };
  gbp: {
    head: Head;
    charts: MonthlyChart[];
    splits: SplitView[];
    terms: TermsView | null;
    actions: ActionsTable | null;
    locations: LocationLine[];
  } | null;
  search: { head: Head; view: SearchView } | null;
  visits: { head: Head; chart: MonthlyChart } | null;
  reviews: { head: Head; view: ReviewsView } | null;
  work: { head: Head; lines: WorkLine[] } | null;
  ahead: { head: Head; paragraphs: string[] } | null;
  notes: {
    head: Head;
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
  const client = report.client_name;
  const period = periodOf(snapshot.period);
  const periodName = periodLabel(period);
  const results = report.search_results ?? null;
  const versus = comparedText(snapshot);
  const card = scorecard(snapshot, results);
  const chartOf = (
    key: SeriesKey,
    title: string,
    comparison: CountComparison | null,
  ) => monthlyChart(snapshot, key, title, comparison);
  const charts = (specs: [SeriesKey, string, CountComparison | null][]) =>
    specs.flatMap(([key, title, comparison]) => {
      const chart = chartOf(key, title, comparison);
      return chart ? [chart] : [];
    });
  const sync: string[] = [];
  const when = (iso: string | null | undefined, source: string) =>
    iso ? sync.push(`${source} last synced ${dateText(iso)}.`) : undefined;
  when(snapshot.sync.gbp, "Google Business Profile");
  when(snapshot.sync.search_console, "Search Console");
  when(snapshot.sync.analytics, "Google Analytics");
  const gbpShown = snapshot.gbp.availability !== "unavailable";
  const compared = comparedLabel(snapshot);
  const searchCharts = charts([
    ["search_clicks", "Search clicks by month", snapshot.search_console.clicks],
    [
      "search_impressions",
      "Search impressions by month",
      snapshot.search_console.impressions,
    ],
  ]);
  const search = searchView(snapshot, results, searchCharts);
  const visitsChart =
    snapshot.analytics.availability !== "unavailable"
      ? chartOf(
          "organic_sessions",
          "Visits from search by month",
          snapshot.analytics.organic_sessions,
        )
      : null;
  const reviews = reviewsView(snapshot);
  const work = workLines(snapshot);
  const cards = report.narrative.result_cards.map((item) =>
    glanceCard(item, snapshot),
  );
  const prose = narrativeParagraphs(report.narrative.what_changed);
  const ahead = narrativeParagraphs(report.narrative.next_work);
  const names = report.profile_names;
  const milestones = report.milestones;
  return {
    draft: report.status === "draft",
    cover: {
      kicker: ["Lilos Growth", client, ...(names.length > 1 ? names : [])].join(
        " · ",
      ),
      title: `${periodName} performance report`,
      intro: `How ${client} performed in ${periodName}, compared with ${versus}.`,
      preparedBy: "Lilos Growth",
      preparedOn: longDay(report.approved_at ?? report.created_at),
      milestones: milestones.length
        ? [
            ...milestones.map((item) => ({
              date: PLAIN_DAY(item.day),
              label: item.label,
            })),
            { date: periodName, label: "The period this report covers." },
          ]
        : null,
    },
    glance:
      cards.length || prose.length
        ? {
            head: {
              kicker: "Summary",
              title: `${periodName} at a glance`,
              intro: cards.length
                ? "The results that matter most this period, each with what it means."
                : "What changed this period and why it matters.",
              measured: "",
              compared: null,
            },
            cards,
            prose,
          }
        : null,
    scorecard: {
      head: {
        kicker: "Scorecard",
        title: "How the numbers moved",
        intro: `Each row states what was measured, where it comes from and what it is compared with. Figures compare ${periodName} with ${versus}.`,
        measured: `${periodName}${snapshot.comparison.compared_as === "monthly_average" ? ", as monthly averages" : ""}`,
        compared: compared,
      },
      card,
    },
    gbp: gbpShown
      ? {
          head: {
            kicker: "Google profile",
            title: "How people found and used the Google profile",
            intro:
              "The Google profile is the front door for a local business. It is where many people check hours, photos and the menu, and where they decide to call, visit the website or get directions.",
            measured: "Google Business Profile Performance data, by month",
            compared,
          },
          charts: charts([
            [
              "profile_views",
              "Profile views by month",
              snapshot.gbp.profile_views.total,
            ],
            [
              "profile_actions",
              "Profile actions by month",
              snapshot.gbp.actions.total,
            ],
          ]),
          splits: splitViews(snapshot),
          terms: termsView(snapshot),
          actions: actionsByMonth(snapshot),
          locations: locationLines(snapshot),
        }
      : null,
    search: search
      ? {
          head: {
            kicker: "Search topics",
            title: `Getting found by people who aren’t searching for ${client}`,
            intro:
              "Non-branded searches are the ones that don’t include the business’s name. These are people deciding where to go, and they are the new customers a business wants to reach.",
            measured: search.coverage,
            compared: search.comparable
              ? `${periodName} vs. ${compared}`
              : null,
          },
          view: search,
        }
      : null,
    visits: visitsChart
      ? {
          head: {
            kicker: "Website visits",
            title: "Visits that began with a Google search",
            intro:
              "Visits to the website that started from an unpaid Google search, month by month.",
            measured: "Google Analytics, search visits, by month",
            compared,
          },
          chart: visitsChart,
        }
      : null,
    reviews: reviews
      ? {
          head: {
            kicker: "Reviews",
            title: "What customers are saying",
            intro:
              "Reviews are one of the first things people read before choosing. This shows the rating, how many new reviews arrived and how many were answered.",
            measured: "Google reviews",
            compared,
          },
          view: reviews,
        }
      : null,
    work: work.length
      ? {
          head: {
            kicker: "Work completed",
            title: "What we did this period",
            intro: `The work finished in ${periodName}, counted from the platform’s own records.`,
            measured: "Finished work recorded in the platform",
            compared: null,
          },
          lines: work,
        }
      : null,
    ahead: ahead.length
      ? {
          head: {
            kicker: "Looking ahead",
            title: "What we’re building next",
            intro: "What happens next to keep results growing.",
            measured: "",
            compared: null,
          },
          paragraphs: ahead,
        }
      : null,
    notes: {
      head: {
        kicker: "Notes",
        title: "Notes and definitions",
        intro: "",
        measured: "",
        compared: null,
      },
      definitions: definitions(snapshot, client),
      dataNotes: snapshot.notes.map(noteText),
      footnotes: card.footnotes,
      sync,
      notIncluded: notIncluded(snapshot),
      period: `${periodName} (${rangeOf(snapshot)}). Compared with ${versus}.`,
    },
  };
}
function rangeOf(snapshot: ReportSnapshot) {
  const { start, end } = snapshot.gbp.current_range;
  return `${dateText(start)} – ${dateText(end)}`;
}
/** The comparison in words: "the month before (July 2026)" or "the same months last year". */
function comparedText(snapshot: ReportSnapshot): string {
  const label = comparedLabel(snapshot);
  const { basis, compared_as: as } = snapshot.comparison;
  if (basis === "custom_baseline")
    return `${label}${as === "monthly_average" ? ", as monthly averages" : ""}`;
  return comparisonText(snapshot);
}
