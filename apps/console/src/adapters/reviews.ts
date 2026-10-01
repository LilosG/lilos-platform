import { z } from "zod";
import type { components } from "@lilos/contracts/api";
const nullable = z.string().nullable();
const item = z.object({
  id: z.uuid(),
  location_id: z.uuid(),
  revision_id: z.uuid().nullable(),
  revision: z.number().int().positive(),
  provider: z.string(),
  external_review_id: z.string(),
  reviewer_reference: nullable,
  rating: z.number().min(0).max(5).nullable(),
  body: nullable,
  title: nullable,
  status: z.string(),
  sentiment: z.string(),
  risk_level: z.string(),
  created_at: z.string(),
  last_synced_at: z.string(),
  response_status: nullable,
});
const history = z.object({
  id: z.uuid(),
  event_type: z.string(),
  action: z.string(),
  result: z.string(),
  occurred_at: z.string(),
  summary: z.string(),
  actor_type: z.string(),
});
const workspace = z.object({
  organization_id: z.uuid(),
  location_id: z.uuid().nullable(),
  locations: z.array(z.object({ id: z.uuid(), name: z.string() })),
  source: z
    .object({
      provider: z.literal("google_business_profile"),
      connection_status: z.string(),
      mapping_status: z.string(),
      last_ingested_at: nullable,
      freshness: z.enum(["fresh", "stale", "unavailable"]),
      quality: z.enum(["partial", "unavailable"]),
      limitation: z.literal("persisted_inventory_not_provider_total"),
    })
    .nullable(),
  inventory_count: z.number().int().nonnegative().nullable(),
  average_rating: z.number().nullable(),
  open_restricted_cases: z.number().int().nonnegative().nullable(),
  items: z.array(item),
  next_offset: z.number().int().nonnegative().nullable(),
  can_ingest: z.boolean(),
  campaigns: z.literal("unavailable_no_canonical_source"),
});
const detail = z.object({
  organization_id: z.uuid(),
  location_id: z.uuid(),
  review: item,
  source: z.object({
    provider: z.literal("google_business_profile"),
    connection_status: z.string(),
    mapping_status: z.string(),
    last_ingested_at: nullable,
    freshness: z.enum(["fresh", "stale", "unavailable"]),
    quality: z.enum(["partial", "unavailable"]),
    limitation: z.literal("persisted_inventory_not_provider_total"),
  }),
  facts: z.array(z.object({ id: z.uuid(), key: z.string(), value: z.json() })),
  can_draft: z.boolean(),
  can_ai_draft: z.boolean(),
  can_read_audit: z.boolean(),
  history: z.array(history),
  recovery: z.literal(
    "canonical_worker_retry_and_ingestion_readback_no_manual_retry_endpoint",
  ),
  policy_override: z.literal("unavailable_no_approval_free_local_policy"),
  responses: z.array(
    z.object({
      id: z.uuid(),
      revision: z.number().int().positive(),
      review_revision_id: z.uuid(),
      text: z.string(),
      status: z.enum([
        "draft",
        "generated",
        "awaiting_approval",
        "approved",
        "publishing",
        "published",
        "failed",
        "rejected",
        "superseded",
        "reconciliation_required",
      ]),
      generated_by: z.string(),
      approved_at: nullable,
      published_at: nullable,
      external_response_id: nullable,
      safe_error_code: nullable,
      workflow_id: z.uuid().nullable(),
      workflow_status: nullable,
      workflow_failure: nullable,
      approval_required: z.boolean(),
      policy_code: z.enum([
        "canonical_local_response_approval",
        "provider_observation_no_local_approval",
      ]),
      can_approve: z.boolean(),
      can_publish: z.boolean(),
      history: z.array(history),
    }),
  ),
});
export type ReviewsView = z.infer<typeof workspace>;
export type ReviewDetailView = z.infer<typeof detail>;
export function adaptReviews(
  raw: unknown,
  org: string,
  location?: string,
): ReviewsView {
  const view = workspace.parse(
    raw,
  ) satisfies components["schemas"]["ReviewsWorkspace"];
  if (
    view.organization_id !== org ||
    (location && view.location_id !== location) ||
    !view.locations.some((l) => l.id === view.location_id) ||
    view.items.some((r) => r.location_id !== view.location_id)
  )
    throw new Error("REVIEW_SCOPE_MISMATCH");
  return view;
}
export function adaptReviewDetail(
  raw: unknown,
  org: string,
  location: string,
  review: string,
): ReviewDetailView {
  const view = detail.parse(
    raw,
  ) satisfies components["schemas"]["ReviewDetail"];
  if (
    view.organization_id !== org ||
    view.location_id !== location ||
    view.review.location_id !== location ||
    view.review.id !== review
  )
    throw new Error("REVIEW_SCOPE_MISMATCH");
  return view;
}
export function metric(value: number | null): string {
  return value === null ? "Unavailable" : String(value);
}
