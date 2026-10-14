import { z } from "zod";
import type { components } from "@lilos/contracts/api";
type Schemas = components["schemas"];
export type ReportStatus = Schemas["ReportStatus"];
export type ReportReadiness = Schemas["ReportReadiness"];
export type NoteCode = Schemas["NoteCode"];
export type SectionKey = Schemas["SectionKey"];
export type UnavailableReason = Schemas["UnavailableReason"];
export type SplitKey = Schemas["SplitKey"];
export type WorkKind = Schemas["WorkKind"];
export type NarrativeFailureCode = Schemas["NarrativeFailureCode"];
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
  "gbp_month_not_synced",
  "gbp_month_partial",
  "gbp_sync_failed",
  "gbp_location_not_mapped",
  "gbp_search_terms_unavailable",
  "gbp_previous_month_incomplete",
  "gbp_year_ago_unavailable",
  "reviews_not_synced",
  "search_console_not_connected",
  "search_console_not_synced",
  "search_console_lag_days",
  "search_console_previous_month_unavailable",
  "analytics_not_connected",
  "analytics_not_synced",
  "analytics_organic_unavailable",
  "analytics_previous_month_unavailable",
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
] as const;
const reason = codes<UnavailableReason>()(REASONS);
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
] as const;
const failureCode = codes<NarrativeFailureCode>()(FAILURE_CODES);
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
    previous: countFigure,
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
    previous: rateFigure,
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
    previous_range: range,
    year_ago_range: range,
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
            })
            .strict(),
        ),
        optional: z.array(
          z
            .object({
              metric,
              comparison: countComparison,
              reported: z.boolean(),
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
    new_in_month: countFigure,
    average_rating_in_month: rateFigure,
    average_rating_overall: rateFigure,
    total_count: countFigure,
    responses_published: countFigure,
    responded_to_new: countFigure,
    response_rate_percent: rateFigure,
    distribution_overall: stars,
    distribution_month: stars,
  })
  .strict();
const searchRow = {
  clicks: z.number().int(),
  impressions: z.number().int(),
  ctr: z.number().nullable(),
  position: z.number().nullable(),
  previous_clicks: nullableInt,
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
      z.object({ query: z.string(), ...searchRow }).strict(),
    ),
    top_pages: z.array(z.object({ page: z.string(), ...searchRow }).strict()),
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
  })
  .strict();
const snapshot = z
  .object({
    schema_version: z.number().int(),
    month: day,
    readiness,
    notes: z.array(note),
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
  })
  .strict();
const narrative = z
  .object({
    what_changed: z.string(),
    next_work: z.string(),
    origin: z.enum(["none", "hermes", "manual"]),
  })
  .strict();
const delivery = z.object({ sent_on: day, recorded_at: z.string() }).strict();
const permissions = z
  .object({ can_generate: z.boolean(), can_publish: z.boolean() })
  .strict();
const revisionRow = z
  .object({
    month: day,
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
    month: day,
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
  })
  .strict();
const generateResult = z
  .object({ report: detailSchema, created: z.boolean() })
  .strict();
export type ReportSnapshot = z.infer<typeof snapshot>;
export type ReportNarrative = z.infer<typeof narrative>;
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
/** One stored revision, exactly as saved. The month, revision and client must be the ones asked for. */
export function adaptReportDetail(
  raw: unknown,
  want: { organization: string; month?: string; revision?: number },
): ReportDetail {
  const view = detailSchema.parse(raw) satisfies Schemas["ReportDetailView"];
  if (
    view.organization_id !== want.organization ||
    (want.month && view.month !== want.month) ||
    (want.revision && view.revision !== want.revision) ||
    view.snapshot.month !== view.month ||
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
