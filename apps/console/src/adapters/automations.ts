import { z } from "zod";
import type { components } from "@lilos/contracts/api";
type Schemas = components["schemas"];
export type AutomationReason = Schemas["AutomationReason"];
export type RecoveryAction = Schemas["RecoveryAction"];
export type WorkflowTypeCode = Schemas["WorkflowTypeCode"];
export type AutomationSource = Schemas["AutomationSource"];
export type AutomationStatus = Schemas["AutomationStatus"];
export type RunOutcome = Schemas["RunOutcome"];
export type RunStatus = Schemas["RunStatus"];
export type FrequencyKind = Schemas["FrequencyKind"];
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
export const REASONS = [
  "GBP_PERFORMANCE_ACCESS_DENIED",
  "INTEGRATION_RECONNECT_REQUIRED",
  "GBP_SCOPE_REQUIRED",
  "GBP_INTEGRATION_NOT_FOUND",
  "NO_CONNECTED_INTEGRATION",
  "TOKEN_REFRESH_FAILED",
  "SECRET_RESOLUTION_FAILED",
  "TOKEN_RESOLUTION_FAILED",
  "GBP_LOCATION_NOT_FOUND",
  "GBP_LOCATION_AMBIGUOUS",
  "GBP_LOCATION_NO_PLATFORM_LINK",
  "LOCATION_ID_INVALID",
  "LOCATION_ID_MISSING",
  "GBP_PERFORMANCE_REQUEST_REJECTED",
  "GBP_PERFORMANCE_RATE_LIMITED",
  "GBP_PERFORMANCE_PROVIDER_UNAVAILABLE",
  "GBP_PERFORMANCE_RESPONSE_INVALID",
  "GBP_PERFORMANCE_KEYWORDS_UNAVAILABLE",
  "GBP_PERFORMANCE_SYNC_FAILED",
  "GBP_SYNC_FAILED",
  "REVIEWS_INGEST_FAILED",
  "SEARCH_CONSOLE_SCOPE_REQUIRED",
  "SEARCH_PROPERTY_NOT_FOUND",
  "SEARCH_PROPERTY_NOT_CONFIGURED",
  "SEARCH_PROPERTY_ID_INVALID",
  "SEARCH_CONSOLE_SYNC_INCOMPLETE",
  "SEARCH_CONSOLE_SYNC_FAILED",
  "ANALYTICS_SCOPE_REQUIRED",
  "ANALYTICS_PROPERTY_NOT_FOUND",
  "ANALYTICS_NOT_CONFIGURED",
  "ANALYTICS_PROPERTY_ID_INVALID",
  "ANALYTICS_SYNC_INCOMPLETE",
  "ANALYTICS_SYNC_FAILED",
  "SEO_ACTIVE_WEBSITE_MISSING",
  "SEO_WEBSITE_NOT_FOUND",
  "SEO_WEBSITE_NOT_ACTIVE",
  "SEO_WEBSITE_SCOPE_MISMATCH",
  "SEO_CRAWL_EMPTY",
  "SEO_ANALYSIS_FAILED",
  "SEO_CRAWL_FAILED",
  "SEO_CRAWL_NOT_TERMINAL",
  "SEO_CRAWL_RUN_NOT_FOUND",
  "MISSING_CRAWL_RUN_ID",
  "INVALID_CRAWL_RUN_ID",
  "GBP_POST_GROUNDING_REQUIRED",
  "GBP_POST_GENERATION_FAILED",
  "GBP_POST_DELIVERY_BINDING_MISSING",
  "GBP_REVIEW_SOURCE_INVALID",
  "GBP_ORGANIZATION_UNAVAILABLE",
  "GBP_POST_REVISION_UNAVAILABLE",
  "GBP_WEBSITE_TARGET_UNAVAILABLE",
  "GBP_WEBSITE_KNOWLEDGE_UNAVAILABLE",
  "GBP_DRIVE_MEDIA_NOT_CONFIGURED",
  "GBP_DRIVE_NO_ELIGIBLE_IMAGE",
  "GBP_DRIVE_MEDIA_UNAVAILABLE",
  "GBP_DRIVE_MEDIA_PROXY_UNAVAILABLE",
  "GBP_DRIVE_UNREACHABLE",
  "GBP_DRIVE_TEMPORARILY_UNAVAILABLE",
  "HERMES_SCOPED_SESSION_BUSY",
  "VERIFICATION_CONTENT_PENDING",
  "VERIFICATION_REREAD_FAILED",
  "WORKFLOW_VERSION_NOT_EXECUTABLE",
  "WORKFLOW_HANDLER_NOT_REGISTERED",
  "WORKFLOW_RUN_MISSING",
  "WORKFLOW_CANCELLED",
  "HANDLER_EXCEPTION",
  "DATABASE_DETERMINISTIC_ERROR",
  "RUN_ESCALATED",
  "RUN_WAITING_APPROVAL",
  "RUN_PARTIALLY_COMPLETED",
  "RUN_EXPIRED",
  "UNMAPPED",
] as const;
const reason = codes<AutomationReason>()(REASONS);
const action = codes<RecoveryAction>()([
  "reconnect_google_business_profile",
  "check_analytics_connection",
  "check_search_console_connection",
  "connect_website",
  "check_location_mapping",
]);
export const WORKFLOW_TYPES = [
  "content.publish",
  "content.draft_revision",
  "content.compose",
  "seo.crawl_or_analysis",
  "seo.analyze",
  "seo.sync_search_console",
  "insights.sync_analytics",
  "seo.apply_site_change",
  "gbp.generate_post",
  "gbp.publish_change",
  "gbp.publish_post",
  "gbp.upload_media",
  "gbp.publish_special_hours",
  "reviews.publish_response",
  "leads.send_communication",
  "gbp.sync",
  "gbp.sync_performance",
  "reviews.ingest",
  "agent.gbp",
  "agent.seo",
  "agent.content",
  "agent.reviews",
  "agent.leads",
  "agent.insights",
  "agent.growth",
] as const;
const workflowType = codes<WorkflowTypeCode>()(WORKFLOW_TYPES);
const source = codes<AutomationSource>()([
  "google_business_profile",
  "reviews",
  "website",
  "analytics",
  "search_console",
  "leads",
  "platform",
]);
export const STATUSES = [
  "needs_attention",
  "running",
  "healthy",
  "paused",
  "not_run_yet",
] as const;
const status = codes<AutomationStatus>()(STATUSES);
const outcome = codes<RunOutcome>()([
  "succeeded",
  "partial",
  "failed",
  "will_retry",
  "needs_decision",
  "cancelled",
  "expired",
  "in_progress",
]);
const runStatus = codes<RunStatus>()([
  "created",
  "queued",
  "running",
  "waiting",
  "waiting_approval",
  "retry_scheduled",
  "completed",
  "partially_completed",
  "cancelled",
  "expired",
  "failed",
  "escalated",
]);
const frequencyKind = codes<FrequencyKind>()([
  "interval_minutes",
  "hourly",
  "interval_hours",
  "daily",
  "weekly",
  "monthly",
  "custom",
]);
const nullableTime = z.string().nullable();
const item = z
  .object({
    id: z.uuid(),
    workflow_type: workflowType,
    client: z.object({ id: z.uuid(), name: z.string(), slug: z.string() }),
    location: z.object({ id: z.uuid(), name: z.string() }).nullable(),
    frequency: z.object({
      kind: frequencyKind,
      interval: z.number().int().nullable(),
      hour: z.number().int().nullable(),
      minute: z.number().int().nullable(),
      weekday: z.number().int().nullable(),
      day_of_month: z.number().int().nullable(),
      timezone: z.string(),
    }),
    status,
    latest_run: z
      .object({
        status: runStatus,
        outcome,
        reason: reason.nullable(),
        started_at: nullableTime,
        finished_at: nullableTime,
      })
      .nullable(),
    next_run_at: nullableTime,
    source,
    attention: z
      .object({
        reason,
        recovery_actions: z.array(action),
        occurred_at: nullableTime,
      })
      .nullable(),
    run_now_allowed: z.boolean(),
  })
  .strict();
const list = z.object({
  generated_at: z.string(),
  counts: z.object({
    total: z.number().int().nonnegative(),
    healthy: z.number().int().nonnegative(),
    needs_attention: z.number().int().nonnegative(),
    running: z.number().int().nonnegative(),
    paused: z.number().int().nonnegative(),
    not_run_yet: z.number().int().nonnegative(),
  }),
  data: z.array(item),
});
const detail = item.extend({
  runs: z.array(
    z.object({
      id: z.uuid(),
      status: runStatus,
      outcome,
      reason: reason.nullable(),
      started_at: nullableTime,
      finished_at: nullableTime,
      duration_seconds: z.number().int().nonnegative().nullable(),
    }),
  ),
});
export type AutomationItem = z.infer<typeof item>;
export type AutomationsView = z.infer<typeof list>;
export type AutomationDetailView = z.infer<typeof detail>;
export type AutomationRun = AutomationDetailView["runs"][number];
export function adaptAutomations(
  raw: unknown,
  organization?: string,
): AutomationsView {
  const view = list.parse(raw) satisfies Schemas["AutomationList"];
  const counted = (wanted: AutomationStatus) =>
    view.data.filter((row) => row.status === wanted).length;
  if (
    view.counts.total !== view.data.length ||
    view.counts.needs_attention !== counted("needs_attention") ||
    view.counts.healthy !== counted("healthy") ||
    view.counts.running !== counted("running") ||
    view.counts.paused !== counted("paused") ||
    view.counts.not_run_yet !== counted("not_run_yet")
  )
    throw new Error("AUTOMATION_COUNT_MISMATCH");
  if (organization && view.data.some((row) => row.client.id !== organization))
    throw new Error("AUTOMATION_SCOPE_MISMATCH");
  return view;
}
export function adaptAutomationDetail(
  raw: unknown,
  schedule: string,
  organization?: string,
): AutomationDetailView {
  const view = detail.parse(raw) satisfies Schemas["AutomationDetail"];
  if (view.id !== schedule || (organization && view.client.id !== organization))
    throw new Error("AUTOMATION_SCOPE_MISMATCH");
  return view;
}
const runResult = z
  .object({
    schedule_id: z.uuid(),
    run_id: z.uuid(),
    run_status: runStatus,
    replayed: z.boolean(),
  })
  .strict();
export function adaptRunResult(raw: unknown, schedule: string) {
  const result = runResult.parse(raw) satisfies Schemas["RunNowResult"];
  if (result.schedule_id !== schedule)
    throw new Error("AUTOMATION_SCOPE_MISMATCH");
  return result;
}
