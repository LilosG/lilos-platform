import { z } from "zod";
import type { components } from "@lilos/contracts/api";
export type OpportunityView = components["schemas"]["OpportunityView"];
export type AttentionView = components["schemas"]["AttentionView"];
export type OpportunityDetail = components["schemas"]["OpportunityDetail"];
const uuid = z.uuid();
const opportunity = z.object({
  id: z.string(),
  source_kind: z.literal("seo_opportunity"),
  source_id: uuid,
  organization_id: uuid,
  location_id: uuid.nullable(),
  website_id: uuid,
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
});
export function adaptOpportunities(
  payload: unknown,
  organizationId: string,
): OpportunityView[] {
  const parsed = z
    .object({ data: z.array(opportunity), next_offset: z.number().nullable() })
    .parse(payload);
  for (const row of parsed.data)
    if (
      row.organization_id !== organizationId ||
      row.id !== `seo_opportunity:${row.source_id}`
    )
      throw new Error("SOURCE_SCOPE_INVALID");
  return parsed.data as OpportunityView[];
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
export function adaptDetail(
  payload: unknown,
  organizationId: string,
  sourceId: string,
): OpportunityDetail {
  const parsed = z
    .object({
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
      can_recommend: z.boolean(),
      can_approve: z.boolean(),
      correlation_id: z.string(),
    })
    .parse(payload);
  adaptOpportunities(
    { data: [parsed.data], next_offset: null },
    organizationId,
  );
  if (
    parsed.data.source_id !== sourceId ||
    parsed.recommendations.some((rev) =>
      rev.change_set.some((edit) => edit.page_id !== parsed.data.page_id),
    )
  )
    throw new Error("SOURCE_SCOPE_INVALID");
  return parsed as OpportunityDetail;
}
export const displayEvidence = (value: unknown): string =>
  value == null
    ? "Unavailable"
    : typeof value === "string"
      ? value
      : JSON.stringify(value, null, 2);
