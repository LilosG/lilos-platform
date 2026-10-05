import { z } from "zod";
import type { components } from "@lilos/contracts/api";
export type AttentionView = components["schemas"]["AttentionView"];
const uuid = z.uuid();
const kind = z.enum(["seo", "content", "growth"]);
const sourceKind = z.enum([
  "seo_opportunity",
  "content_opportunity",
  "growth_initiative",
]);
const prefix = {
  seo: "seo_opportunity",
  content: "content_opportunity",
  growth: "growth_initiative",
} as const;
const evidenceSummary = z.object({
  source: z.string().nullable(),
  signal: z.string(),
  metrics: z.array(z.object({ key: z.string(), value: z.number() })),
  source_count: z.number().int().nullable().optional(),
});
const subject = z.object({
  query: z.string().nullable(),
  path: z.string().nullable(),
});
const earlierObservation = z.object({
  id: uuid,
  observed_at: z.string(),
  status: z.string(),
  priority: z.number().nullable(),
});
const opportunity = z.object({
  id: z.string(),
  source_kind: sourceKind,
  kind,
  source_id: uuid,
  organization_id: uuid,
  client: z
    .object({ organization_id: uuid, name: z.string(), slug: z.string() })
    .nullable(),
  location_id: uuid.nullable(),
  website_id: uuid.nullable(),
  page_id: uuid.nullable(),
  classification: z.enum([
    "Issue",
    "Growth Opportunity",
    "Optimization",
    "Data & Tracking",
  ]),
  source_type: z.string(),
  status: z.string(),
  priority: z.number().nullable(),
  evidence: z.record(z.string(), z.unknown()),
  score_explanation: z.record(z.string(), z.unknown()),
  observed_at: z.string(),
  evidence_context: z.object({
    source: z.string().nullable(),
    quality: z.string().nullable(),
    freshness_at: z.string().nullable(),
    period_start: z.string().nullable(),
    period_end: z.string().nullable(),
    limitation_code: z.string().nullable(),
  }),
  priority_band: z.enum(["high", "medium", "low"]).nullable(),
  headline: z.string().nullable(),
  confidence: z.number().nullable(),
  evidence_summary: evidenceSummary.nullable(),
  next_action: z.enum([
    "request_recommendation",
    "review_recommendation",
    "monitor_publication",
    "measure_impact",
    "review_opportunity",
    "review_growth_plan",
    "monitor_execution",
    "none",
  ]),
  latest_revision_status: z.string().nullable(),
  site_change: z.enum(["configured", "not_configured", "not_applicable"]),
  site_change_reason: z.literal("SITE_CHANGES_NOT_CONFIGURED").nullable(),
  subject,
  summary: z.string().nullable(),
  lifecycle: z.enum(["open", "live", "done"]),
  verified_at: z.string().nullable(),
  importance_reason: z.literal("KEY_EVENTS_INFERRED").nullable(),
  earlier_observations: z.array(earlierObservation),
});
export type OpportunityKind = z.infer<typeof kind>;
export type OpportunityView = z.infer<typeof opportunity>;
function assertScope(
  rows: z.infer<typeof opportunity>[],
  organizationId: string | null,
) {
  for (const row of rows)
    if (
      (organizationId !== null && row.organization_id !== organizationId) ||
      row.id !== `${prefix[row.kind]}:${row.source_id}` ||
      row.source_kind !== prefix[row.kind] ||
      (row.client && row.client.organization_id !== row.organization_id)
    )
      throw new Error("SOURCE_SCOPE_INVALID");
}
export function adaptOpportunities(
  payload: unknown,
  organizationId: string,
): OpportunityView[] {
  const parsed = z
    .object({ data: z.array(opportunity), next_offset: z.number().nullable() })
    .parse(payload);
  assertScope(parsed.data, organizationId);
  return parsed.data;
}
const list = z.object({
  data: z.array(opportunity),
  next_offset: z.number().int().nullable(),
  kinds_unavailable: z.array(kind),
});
export interface OpportunityListView {
  items: OpportunityView[];
  next: number | null;
  kindsUnavailable: OpportunityKind[];
}
/** The unified list. A portfolio read has no single organization; each row carries its client. */
export function adaptOpportunityList(
  payload: unknown,
  organizationId: string | null,
  allowed: readonly string[] | null,
): OpportunityListView {
  const parsed = list.parse(payload);
  assertScope(parsed.data, organizationId);
  if (
    allowed !== null &&
    parsed.data.some(
      (row) => !row.client || !allowed.includes(row.client.organization_id),
    )
  )
    throw new Error("SOURCE_SCOPE_INVALID");
  return {
    items: parsed.data,
    next: parsed.next_offset,
    kindsUnavailable: parsed.kinds_unavailable,
  };
}
const attention = z.object({
  id: z.string(),
  source_id: uuid,
  opportunity_id: uuid,
  reason: z.enum([
    "waiting_approval",
    "publication_blocked",
    "workflow_failure",
    "retry_scheduled",
    "waiting",
    "missing_mapping",
  ]),
  status: z.string(),
  code: z.string().nullable(),
});
export function adaptAttention(payload: unknown): AttentionView[] {
  return z
    .object({ data: z.array(attention), next_offset: z.number().nullable() })
    .parse(payload).data;
}
const change = z.object({
  page_id: uuid,
  field: z.enum([
    "seo_title",
    "meta_description",
    "h1",
    "body_section",
    "schema",
    "internal_link",
  ]),
  current_value: z.string(),
  proposed_value: z.string(),
  rationale: z.string(),
});
const quality = z.object({
  state: z.enum(["passed", "blocked", "unavailable"]),
  problems: z.array(
    z.object({ field: z.string(), code: z.string(), reason: z.string() }),
  ),
  target_query: z.string().nullable(),
  top_queries: z.array(z.string()),
  location_terms: z.array(z.string()),
  repository_verification: z.literal("executor_rechecks_before_write"),
});
const publication = z.object({
  publication_id: uuid.nullable(),
  workflow_run_id: uuid.nullable(),
  deployment_status: z.string().nullable(),
  approved_head_sha: z.string().nullable(),
  external_revision_id: z.string().nullable(),
  published_url: z.string().nullable(),
  verified_at: z.string().nullable(),
  mapping_state: z.string().nullable(),
  blocked_code: z.string().nullable(),
  publication_status: z.string().nullable(),
  pull_request_url: z
    .string()
    .regex(
      /^https:\/\/github\.com\/[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+\/pull\/\d+$/,
    )
    .nullable(),
  build_gate: z.string().nullable(),
  build_state: z.string().nullable(),
  verification_state: z.string().nullable(),
  live_checks: z.array(
    z.object({
      field: z.string().nullable(),
      expected: z.unknown(),
      observed: z.unknown(),
      state: z.string().nullable(),
    }),
  ),
});
const revision = z.object({
  id: uuid,
  created_at: z.string(),
  revision_number: z.number().int(),
  proposed_action: z.string(),
  expected_result_hypothesis: z.string(),
  risk: z.string(),
  effort: z.string(),
  status: z.enum([
    "awaiting_approval",
    "approved",
    "rejected",
    "superseded",
    "withdrawn",
    "implemented",
  ]),
  change_set: z.array(change),
  change_set_limitation_code: z.string().nullable(),
  decision_context: z.record(z.string(), z.unknown()).nullable(),
  site_change: publication.nullable(),
  approved_fingerprint: z.string().nullable(),
  quality,
});
const growthPlan = z.object({
  objective: z.string(),
  rationale: z.string(),
  confidence: z.number(),
  actions: z.array(
    z.object({
      id: uuid,
      action_key: z.string(),
      product_key: z.string(),
      action_type: z.string(),
      execution_mode: z.string(),
      status: z.string(),
      risk: z.string(),
      effort: z.string(),
      expected_result_hypothesis: z.string(),
      safe_error_code: z.string().nullable(),
    }),
  ),
});
const contentView = z.object({
  target_reference: z.string(),
  opportunity_type: z.string(),
  items: z.array(
    z.object({
      id: uuid,
      content_type: z.string(),
      title: z.string(),
      status: z.string(),
    }),
  ),
});
const history = z.array(
  z.object({
    event_type: z.string(),
    action: z.string(),
    result: z.string(),
    occurred_at: z.string(),
    actor_type: z.string(),
  }),
);
const liveCheck = z.object({
  state: z.string().nullable(),
  verified_at: z.string().nullable(),
  checks: publication.shape.live_checks,
});
const detailSchema = z.object({
  kind,
  data: opportunity,
  page_url: z.string().nullable(),
  recommendations: z.array(revision),
  runs: z.array(
    z.object({
      id: uuid,
      task_id: uuid,
      task_status: z.string(),
      status: z.string(),
      correlation_id: z.string(),
      output_reference: z.string().nullable(),
    }),
  ),
  growth: growthPlan.nullable(),
  content: contentView.nullable(),
  history: history.nullable(),
  live_check: liveCheck.nullable(),
  can_recommend: z.boolean(),
  can_approve: z.boolean(),
  correlation_id: z.string(),
});
export type OpportunityDetail = z.infer<typeof detailSchema>;
export function adaptDetail(
  payload: unknown,
  organizationId: string,
  sourceId: string,
): OpportunityDetail {
  const parsed = detailSchema.parse(payload);
  assertScope([parsed.data], organizationId);
  if (
    parsed.data.source_id !== sourceId ||
    parsed.data.kind !== parsed.kind ||
    (parsed.kind === "growth") !== (parsed.growth !== null) ||
    (parsed.kind === "content") !== (parsed.content !== null) ||
    parsed.recommendations.some((rev) =>
      rev.change_set.some((edit) => edit.page_id !== parsed.data.page_id),
    )
  )
    throw new Error("SOURCE_SCOPE_INVALID");
  return parsed;
}
export const displayEvidence = (value: unknown): string =>
  value == null
    ? "Unavailable"
    : typeof value === "string"
      ? value
      : JSON.stringify(value, null, 2);
