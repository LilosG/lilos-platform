import { z } from "zod";
import type { components } from "@lilos/contracts/api";
import {
  comparisonOfSpec,
  sameComparison,
  samePeriod,
  type ComparisonRef,
  type PeriodRef,
} from "../lib/report-period";
type Schemas = components["schemas"];
export type ReportStatus = Schemas["ReportStatus"];
export type ReportReadiness = Schemas["ReportReadiness"];
export type NoteCode = Schemas["NoteCode"];
export type SectionKey = Schemas["SectionKey"];
export type UnavailableReason = Schemas["UnavailableReason"];
export type SplitKey = Schemas["SplitKey"];
export type WorkKind = Schemas["WorkKind"];
export type NarrativeFailureCode = Schemas["NarrativeFailureCode"];
export type ComparisonBasis = Schemas["ComparisonBasis"];
export type ComparedAs = Schemas["ComparedAs"];
export type HeadlineKey = Schemas["HeadlineKey"];
export type SeriesKey = Schemas["SeriesKey"];
export type FigureKey = Schemas["FigureKey"];
export type CardTone = Schemas["CardTone"];
/** Compile-time proof that a list of codes is exactly the contract's enum. */
type Exact<Contract extends string, Listed extends string> = [
  Contract,
] extends [Listed]
  ? [Listed] extends [Contract]
    ? true
    : never
  : never;
function codes<Contract extends string>() {
  return <const L extends readonly [Contract, ...Contract[]]>(
    list: L & (Exact<Contract, L[number]> extends true ? unknown : never),
  ) => z.enum(list as unknown as [Contract, ...Contract[]]);
}
export const NOTE_CODES = [
  "gbp_not_connected",
  "gbp_period_not_synced",
  "gbp_period_partial",
  "gbp_sync_failed",
  "gbp_location_not_mapped",
  "gbp_search_terms_unavailable",
  "gbp_compared_period_incomplete",
  "gbp_year_ago_unavailable",
  "reviews_not_synced",
  "search_console_not_connected",
  "search_console_not_synced",
  "search_console_lag_days",
  "search_console_months_missing",
  "search_console_compared_period_unavailable",
  "search_console_no_data_yet",
  "search_console_compared_as_average",
  "search_console_first_month_partial",
  "analytics_not_connected",
  "analytics_not_synced",
  "analytics_organic_unavailable",
  "analytics_months_missing",
  "analytics_compared_period_unavailable",
  "optional_figure_not_reported",
  "optional_figure_stopped",
] as const;
const noteCode = codes<NoteCode>()(NOTE_CODES);
export const SECTION_KEYS = [
  "profile_views",
  "profile_actions",
  "daily_series",
  "search_terms",
  "locations",
  "reviews",
  "search_console",
  "analytics",
  "local_rank",
  "work_completed",
  "narrative",
] as const;
const sectionKey = codes<SectionKey>()(SECTION_KEYS);
export const REASONS = [
  "not_connected",
  "not_synced",
  "no_data",
  "not_reported",
  "partial_period",
  "no_views",
  "not_tracked",
  "not_compared",
  "source_unavailable",
  "no_search_data_yet",
] as const;
const reason = codes<UnavailableReason>()(REASONS);
export const HEADLINE_KEYS = [
  "profile_views",
  "profile_actions",
  "website_search_clicks",
  "organic_sessions",
  "new_reviews",
  "average_rating",
] as const;
const headlineKey = codes<HeadlineKey>()(HEADLINE_KEYS);
export const SERIES_KEYS = [
  "profile_views",
  "profile_actions",
  "calls",
  "website_clicks",
  "direction_requests",
  "search_clicks",
  "search_impressions",
  "organic_sessions",
  "new_reviews",
] as const;
const seriesKey = codes<SeriesKey>()(SERIES_KEYS);
const comparisonBasis = codes<ComparisonBasis>()([
  "previous_period",
  "same_period_last_year",
  "custom_baseline",
]);
const comparedAs = codes<ComparedAs>()(["total", "monthly_average"]);
const splitKey = codes<SplitKey>()(["maps", "search", "desktop", "mobile"]);
const workKind = codes<WorkKind>()([
  "gbp_post",
  "website_content",
  "review_response",
  "gbp_profile_change",
  "website_change",
]);
export const FAILURE_CODES = [
  "draft_failed",
  "draft_malformed",
  "draft_empty",
  "number_not_in_data",
  "authorship_mentioned",
  "causal_claim",
  "tone_not_supported",
] as const;
const failureCode = codes<NarrativeFailureCode>()(FAILURE_CODES);
export const FIGURE_KEYS = [
  "profile_views",
  "profile_actions",
  "calls",
  "website_clicks",
  "direction_requests",
  "search_clicks",
  "search_impressions",
  "organic_sessions",
  "new_reviews",
  "average_rating",
  "searches_in_top_ten",
  "new_to_page_one",
] as const;
const figureKey = codes<FigureKey>()(FIGURE_KEYS);
const cardTone = codes<CardTone>()(["good", "bad", "neutral"]);
const status = codes<ReportStatus>()(["draft", "ready", "sent"]);
const readiness = codes<ReportReadiness>()([
  "ready",
  "ready_with_note",
  "missing_data",
]);
const availability = z.enum(["available", "partial", "unavailable"]);
const metric = z.enum([
  "BUSINESS_IMPRESSIONS_DESKTOP_MAPS",
  "BUSINESS_IMPRESSIONS_DESKTOP_SEARCH",
  "BUSINESS_IMPRESSIONS_MOBILE_MAPS",
  "BUSINESS_IMPRESSIONS_MOBILE_SEARCH",
  "CALL_CLICKS",
  "WEBSITE_CLICKS",
  "BUSINESS_DIRECTION_REQUESTS",
  "BUSINESS_CONVERSATIONS",
  "BUSINESS_BOOKINGS",
  "BUSINESS_FOOD_ORDERS",
  "BUSINESS_FOOD_MENU_CLICKS",
]);
const nullableInt = z.number().int().nullable();
const day = z.string().regex(/^\d{4}-\d{2}-\d{2}$/);
const uuid = z.uuid();
/** A figure has a value exactly when it is available or partial; missing is never a number. */
const figureRules = (figure: {
  availability: string;
  value?: number | null;
  reason?: string | null;
}) => {
  const hasValue = figure.value !== null && figure.value !== undefined;
  return figure.availability === "unavailable"
    ? !hasValue && !!figure.reason
    : hasValue;
};
const countFigure = z
  .object({
    availability,
    value: nullableInt.optional(),
    reason: reason.nullable().optional(),
    days_covered: nullableInt.optional(),
    days_expected: nullableInt.optional(),
    months_covered: nullableInt.optional(),
    months_expected: nullableInt.optional(),
  })
  .strict()
  .refine(figureRules, { message: "FIGURE_MISSING_IS_NOT_A_NUMBER" });
const rateFigure = z
  .object({
    availability,
    value: z.number().nullable().optional(),
    reason: reason.nullable().optional(),
  })
  .strict()
  .refine(figureRules, { message: "FIGURE_MISSING_IS_NOT_A_NUMBER" });
const countComparison = z
  .object({
    current: countFigure,
    compared: countFigure,
    compared_as: comparedAs,
    current_monthly_average: nullableInt.optional(),
    year_ago: countFigure.nullable().optional(),
    change: nullableInt.optional(),
    change_percent: z.number().nullable().optional(),
    year_change: nullableInt.optional(),
    year_change_percent: z.number().nullable().optional(),
  })
  .strict();
const rateComparison = z
  .object({
    current: rateFigure,
    compared: rateFigure,
    year_ago: rateFigure.nullable().optional(),
    change: z.number().nullable().optional(),
    year_change: z.number().nullable().optional(),
  })
  .strict();
const range = z
  .object({ start: day, end: day, days: z.number().int() })
  .strict();
const gbp = z
  .object({
    availability,
    reason: reason.nullable().optional(),
    current_range: range,
    compared_range: range,
    year_ago_range: range.nullable(),
    through_date: day.nullable(),
    profile_views: z
      .object({
        total: countComparison,
        sources: z.array(
          z.object({ metric, comparison: countComparison }).strict(),
        ),
        maps_search: z
          .object({
            parts: z.array(
              z
                .object({
                  key: splitKey,
                  figure: countFigure,
                  share_percent: z.number().nullable().optional(),
                })
                .strict(),
            ),
          })
          .strict(),
        desktop_mobile: z
          .object({
            parts: z.array(
              z
                .object({
                  key: splitKey,
                  figure: countFigure,
                  share_percent: z.number().nullable().optional(),
                })
                .strict(),
            ),
          })
          .strict(),
      })
      .strict(),
    actions: z
      .object({
        total: countComparison,
        action_rate: rateComparison,
        actions: z.array(
          z
            .object({
              metric,
              comparison: countComparison,
              reported: z.boolean(),
              comparable: z.boolean(),
              note: noteCode.nullable().optional(),
            })
            .strict(),
        ),
        optional: z.array(
          z
            .object({
              metric,
              comparison: countComparison,
              reported: z.boolean(),
              comparable: z.boolean(),
              note: noteCode.nullable().optional(),
            })
            .strict(),
        ),
      })
      .strict(),
    daily: z
      .object({
        availability,
        days_expected: z.number().int(),
        days_synced: z.number().int(),
        missing_days: z.array(day),
        points: z.array(
          z
            .object({
              day,
              views: nullableInt,
              actions: nullableInt,
            })
            .strict(),
        ),
      })
      .strict(),
    search_terms: z
      .object({
        availability,
        reason: reason.nullable().optional(),
        terms: z.array(
          z
            .object({
              keyword: z.string(),
              value: nullableInt,
              below_threshold: nullableInt,
              is_exact: z.boolean(),
            })
            .strict(),
        ),
        total_terms: z.number().int(),
        months_covered: nullableInt.optional(),
        months_expected: nullableInt.optional(),
      })
      .strict(),
    locations: z.array(
      z
        .object({
          location_id: uuid,
          name: z.string(),
          mapped: z.boolean(),
          profile_views: countComparison,
          calls: countComparison,
          website_clicks: countComparison,
          direction_requests: countComparison,
        })
        .strict(),
    ),
  })
  .strict();
const stars = z.array(
  z
    .object({
      stars: z.union([
        z.literal(1),
        z.literal(2),
        z.literal(3),
        z.literal(4),
        z.literal(5),
      ]),
      count: z.number().int(),
    })
    .strict(),
);
const reviews = z
  .object({
    availability,
    reason: reason.nullable().optional(),
    new_reviews: countComparison,
    average_rating_in_period: rateComparison,
    average_rating_overall: rateComparison,
    total_count: countFigure,
    responses_published: countFigure,
    responded_to_new: countFigure,
    response_rate_percent: rateComparison,
    distribution_overall: stars,
    distribution_period: stars,
  })
  .strict();
const searchRow = {
  clicks: z.number().int(),
  impressions: z.number().int(),
  ctr: z.number().nullable(),
  position: z.number().nullable(),
  compared_clicks: nullableInt,
  clicks_change: nullableInt,
};
const searchConsole = z
  .object({
    availability,
    reason: reason.nullable().optional(),
    clicks: countComparison,
    impressions: countComparison,
    ctr_percent: rateComparison,
    average_position: rateComparison,
    top_queries: z.array(
      z
        .object({ query: z.string(), is_branded: z.boolean(), ...searchRow })
        .strict(),
    ),
    top_pages: z.array(z.object({ page: z.string(), ...searchRow }).strict()),
    branded_share_percent: z.number().nullable().optional(),
    lag_days: nullableInt.optional(),
  })
  .strict();
const analytics = z
  .object({
    availability,
    reason: reason.nullable().optional(),
    organic_sessions: countComparison,
  })
  .strict();
const note = z
  .object({
    code: noteCode,
    section: sectionKey,
    count: nullableInt.optional(),
    location_id: uuid.nullable().optional(),
    metric: metric.nullable().optional(),
    month: day.nullable().optional(),
    covered_months: z.array(day).nullable().optional(),
    missing_months: z.array(day).nullable().optional(),
  })
  .strict();
const month = z.string().regex(/^\d{4}-\d{2}-01$/);
const period = z.object({ start_month: month, end_month: month }).strict();
const comparisonSpec = z
  .object({
    basis: comparisonBasis,
    baseline_start: month.nullable().optional(),
    baseline_end: month.nullable().optional(),
  })
  .strict();
const resolvedComparison = z
  .object({
    basis: comparisonBasis,
    compared: period,
    year_ago: period.nullable(),
    compared_as: comparedAs,
  })
  .strict();
const monthPoint = z
  .object({
    month,
    availability,
    value: nullableInt.optional(),
    excluded_from_baseline: z.boolean().default(false),
  })
  .strict()
  .refine(
    (point) =>
      (point.availability === "unavailable") ===
      (point.value === null || point.value === undefined),
    { message: "FIGURE_MISSING_IS_NOT_A_NUMBER" },
  );
const headline = z
  .object({
    key: headlineKey,
    count: countComparison.nullable().optional(),
    rate: rateComparison.nullable().optional(),
  })
  .strict()
  .refine((item) => (item.count ? 1 : 0) + (item.rate ? 1 : 0) === 1, {
    message: "HEADLINE_HAS_ONE_FIGURE",
  });
const sync = z
  .object({
    gbp: day.nullable().optional(),
    search_console: day.nullable().optional(),
    analytics: day.nullable().optional(),
  })
  .strict();
const snapshot = z
  .object({
    schema_version: z.number().int(),
    period,
    comparison: resolvedComparison,
    location_names: z.array(z.string()),
    sync,
    readiness,
    notes: z.array(note),
    headlines: z.array(headline).max(4),
    monthly: z.array(
      z
        .object({
          key: seriesKey,
          period: z.array(monthPoint),
          compared: z.array(monthPoint),
        })
        .strict(),
    ),
    gbp,
    reviews,
    search_console: searchConsole,
    analytics,
    local_rank: z
      .object({
        state: z.enum(["tracked", "not_tracked"]),
        value: nullableInt.optional(),
      })
      .strict(),
    work: z
      .object({
        groups: z.array(
          z
            .object({
              kind: workKind,
              count: z.number().int(),
              titles: z.array(z.string()),
            })
            .strict(),
        ),
      })
      .strict(),
    search_movement: z
      .object({
        comparable: z.boolean(),
        months_covered: z.number().int(),
        months_expected: z.number().int(),
        compared_months_covered: z.number().int(),
        compared_months_expected: z.number().int(),
        queries: z.array(
          z
            .object({
              query: z.string(),
              before_position: z.number().nullable(),
              after_position: z.number().nullable(),
              before_impressions: nullableInt,
              after_impressions: z.number().int(),
              before_clicks: nullableInt,
              after_clicks: z.number().int(),
            })
            .strict(),
        ),
      })
      .strict()
      .nullable()
      .optional(),
  })
  .strict();
const cardFigure = z
  .object({
    key: figureKey,
    unit: z.enum(["count", "stars"]),
    current: z.number(),
    monthly_average: z.boolean(),
    compared: z.number().nullable().optional(),
    change: z.number().nullable().optional(),
    change_percent: z.number().nullable().optional(),
  })
  .strict();
const resultCard = z
  .object({
    figure_keys: z.array(figureKey).min(1).max(2),
    figures: z.array(cardFigure),
    tone: cardTone,
    headline: z.boolean(),
    title: z.string(),
    text: z.string(),
  })
  .strict();
const narrative = z
  .object({
    what_changed: z.string(),
    next_work: z.string(),
    origin: z.enum(["none", "hermes", "manual"]),
    result_cards: z.array(resultCard).max(4),
  })
  .strict();
const topics = z
  .object({
    topics: z.array(
      z
        .object({
          key: z.string(),
          label: z.string(),
          queries: z.array(z.string()),
        })
        .strict(),
    ),
    brand_variants: z.array(z.string()),
  })
  .strict();
const searchResults = z
  .object({
    comparable: z.boolean(),
    months_covered: z.number().int(),
    months_expected: z.number().int(),
    top_ten_before: nullableInt,
    top_ten_after: z.number().int(),
    new_to_page_one: nullableInt,
    clicks_before: nullableInt,
    clicks_after: z.number().int(),
    impressions_before: nullableInt,
    impressions_after: z.number().int(),
    position_before: z.number().nullable(),
    position_after: z.number().nullable(),
    topics: z.array(
      z
        .object({
          key: z.string(),
          label: z.string(),
          examples: z.array(z.string()),
          top_ten_before: nullableInt,
          top_ten_after: z.number().int(),
          position_before: z.number().nullable(),
          position_after: z.number().nullable(),
          clicks_before: nullableInt,
          clicks_after: z.number().int(),
        })
        .strict(),
    ),
    gains: z.array(
      z
        .object({
          key: z.string(),
          label: z.string(),
          rows: z.array(
            z
              .object({
                query: z.string(),
                position_before: z.number().nullable(),
                position_after: z.number(),
                impressions_before: nullableInt,
                impressions_after: z.number().int(),
                clicks_before: nullableInt,
                clicks_after: z.number().int(),
              })
              .strict(),
          ),
        })
        .strict(),
    ),
  })
  .strict();
const delivery = z.object({ sent_on: day, recorded_at: z.string() }).strict();
const permissions = z
  .object({ can_generate: z.boolean(), can_publish: z.boolean() })
  .strict();
const revisionRow = z
  .object({
    period,
    comparison: comparisonSpec,
    revision: z.number().int().min(1),
    status,
    readiness,
    is_current: z.boolean(),
    created_at: z.string(),
    approved_at: z.string().nullable(),
    delivery: delivery.nullable(),
  })
  .strict();
const upcoming = z
  .object({
    kind: z.literal("generate_monthly_report"),
    next_run_at: z.string(),
    month: day,
  })
  .strict();
const listSchema = z
  .object({
    organization_id: uuid,
    current_month: day,
    current: revisionRow.nullable(),
    history: z.array(revisionRow),
    upcoming: upcoming.nullable(),
    permissions,
  })
  .strict();
const detailSchema = z
  .object({
    organization_id: uuid,
    client_name: z.string(),
    client_slug: z.string(),
    period,
    comparison: comparisonSpec,
    revision: z.number().int().min(1),
    revision_count: z.number().int().min(1),
    status,
    readiness,
    is_current: z.boolean(),
    created_at: z.string(),
    approved_at: z.string().nullable(),
    delivery: delivery.nullable(),
    snapshot,
    narrative,
    topics: topics.nullable().optional(),
    search_results: searchResults.nullable().optional(),
    profile_names: z.array(z.string()),
    milestones: z.array(z.object({ day, label: z.string() }).strict()),
    permissions,
  })
  .strict();
const portfolioRow = z
  .object({
    organization_id: uuid,
    slug: z.string(),
    name: z.string(),
    month: day,
    revision: nullableInt,
    status: status.nullable(),
    readiness: readiness.nullable(),
    sent_on: day.nullable(),
  })
  .strict();
const portfolioSchema = z
  .object({
    month: day,
    counts: z
      .object({
        ready: z.number().int(),
        needs_attention: z.number().int(),
        missing_data: z.number().int(),
        sent: z.number().int(),
        not_generated: z.number().int(),
      })
      .strict(),
    clients: z.array(portfolioRow),
  })
  .strict();
const draftResult = z
  .object({
    report: detailSchema,
    outcome: z.enum(["drafted", "not_used"]),
    failure: failureCode.nullable().optional(),
    cards_dropped: z.number().int(),
  })
  .strict();
const generateResult = z
  .object({ report: detailSchema, created: z.boolean() })
  .strict();
export type ReportSnapshot = z.infer<typeof snapshot>;
export type ReportNarrative = z.infer<typeof narrative>;
export type ResultCard = z.infer<typeof resultCard>;
export type SearchResults = z.infer<typeof searchResults>;
export type ReportDetail = z.infer<typeof detailSchema>;
export type ReportList = z.infer<typeof listSchema>;
export type ReportRevisionRow = z.infer<typeof revisionRow>;
export type PortfolioReports = z.infer<typeof portfolioSchema>;
export type PortfolioReportRow = z.infer<typeof portfolioRow>;
export type CountFigure = z.infer<typeof countFigure>;
export type RateFigure = z.infer<typeof rateFigure>;
export type CountComparison = z.infer<typeof countComparison>;
export type RateComparison = z.infer<typeof rateComparison>;
export type ReportNote = z.infer<typeof note>;
export type DraftResult = z.infer<typeof draftResult>;
export function adaptReportList(
  raw: unknown,
  organization: string,
): ReportList {
  const view = listSchema.parse(raw) satisfies Schemas["ReportListView"];
  if (view.organization_id !== organization)
    throw new Error("REPORT_SCOPE_MISMATCH");
  return view;
}
/** One stored revision, exactly as saved. Period, comparison, revision and client must be those asked for. */
export function adaptReportDetail(
  raw: unknown,
  want: {
    organization: string;
    period?: PeriodRef;
    comparison?: ComparisonRef;
    revision?: number;
  },
): ReportDetail {
  const view = detailSchema.parse(raw) satisfies Schemas["ReportDetailView"];
  const stored: PeriodRef = {
    start: view.period.start_month,
    end: view.period.end_month,
  };
  if (
    view.organization_id !== want.organization ||
    (want.period && !samePeriod(want.period, stored)) ||
    (want.comparison &&
      !sameComparison(want.comparison, comparisonOfSpec(view.comparison))) ||
    (want.revision && view.revision !== want.revision) ||
    !samePeriod(stored, {
      start: view.snapshot.period.start_month,
      end: view.snapshot.period.end_month,
    }) ||
    view.snapshot.comparison.basis !== view.comparison.basis ||
    view.snapshot.readiness !== view.readiness
  )
    throw new Error("REPORT_SCOPE_MISMATCH");
  return view;
}
export function adaptDraftResult(raw: unknown): DraftResult {
  return draftResult.parse(raw) satisfies Schemas["ReportNarrativeDraftResult"];
}
export function adaptGenerateResult(raw: unknown) {
  return generateResult.parse(raw) satisfies Schemas["ReportGenerateResult"];
}
export function adaptPortfolioReports(raw: unknown): PortfolioReports {
  const view = portfolioSchema.parse(
    raw,
  ) satisfies Schemas["PortfolioReportsView"];
  const counted = (pick: (row: PortfolioReportRow) => boolean) =>
    view.clients.filter(pick).length;
  const open = (row: PortfolioReportRow) => row.status !== "sent";
  if (
    view.counts.sent !== counted((row) => row.status === "sent") ||
    view.counts.not_generated !== counted((row) => row.status === null) ||
    view.counts.ready !==
      counted((row) => row.readiness === "ready" && open(row)) ||
    view.counts.needs_attention !==
      counted((row) => row.readiness === "ready_with_note" && open(row)) ||
    view.counts.missing_data !==
      counted((row) => row.readiness === "missing_data" && open(row)) ||
    view.clients.some((row) => row.month !== view.month)
  )
    throw new Error("REPORT_COUNT_MISMATCH");
  return view;
}
