import { z } from "zod";
import type { components } from "@lilos/contracts/api";
const nullable = z.string().nullable();
const source = z.object({
  id: z.uuid(),
  name: z.string(),
  source_type: z.string(),
  status: z.string(),
  location_id: z.uuid().nullable(),
  integration_connection_id: z.uuid().nullable(),
  provider: nullable,
  connection_status: nullable,
  last_intake_at: nullable,
  intake_recency: z.enum(["recent", "stale", "unavailable"]),
  sync_state: z.literal("unavailable_no_canonical_sync_record"),
  quality: z.literal("partial"),
  lead_count: z.number().int().nonnegative(),
  recorded_conversions: z.number().int().nonnegative(),
});
const lead = z.object({
  id: z.uuid(),
  location_id: z.uuid().nullable(),
  source_id: z.uuid(),
  status: z.string(),
  urgency: z.string(),
  received_at: z.string(),
  acknowledged_at: nullable,
  first_outbound_attempt_at: nullable,
  first_delivered_at: nullable,
  first_human_contact_at: nullable,
  converted_at: nullable,
  converted_value_cents: z.number().int().nonnegative().nullable(),
  loss_reason: nullable,
  assigned_to_user_id: z.uuid().nullable(),
  duplicate_of_lead_id: z.uuid().nullable(),
  outcome: z.enum(["recorded_conversion", "recorded_loss", "unknown"]),
  attribution: z.literal("source_identity_only_no_campaign_or_landing_page"),
});
const downstream = z.literal(
  "unavailable_no_booking_sales_jobs_or_revenue_source",
);
const workspace = z.object({
  organization_id: z.uuid(),
  location_id: z.uuid().nullable(),
  locations: z.array(z.object({ id: z.uuid(), name: z.string() })),
  sources: z.array(source),
  items: z.array(lead),
  inventory_count: z.number().int().nonnegative().nullable(),
  recorded_conversions: z.number().int().nonnegative().nullable(),
  next_offset: z.number().int().nonnegative().nullable(),
  period: z.literal("all_persisted_records"),
  quality: z.enum(["partial", "unavailable"]),
  downstream_outcomes: downstream,
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
const detail = z.object({
  organization_id: z.uuid(),
  lead: lead.extend({
    first_name: nullable,
    last_name: nullable,
    normalized_email: nullable,
    normalized_phone: nullable,
    message: nullable,
    location_match_status: z.string(),
  }),
  source,
  notes: z.array(
    z.object({
      id: z.uuid(),
      body: z.string(),
      author_user_id: z.uuid().nullable(),
      created_at: z.string(),
    }),
  ),
  tasks: z.array(
    z.object({
      id: z.uuid(),
      title: z.string(),
      description: nullable,
      due_at: nullable,
      assigned_to_user_id: z.uuid().nullable(),
      status: z.string(),
      completed_at: nullable,
    }),
  ),
  consents: z.array(
    z.object({
      id: z.uuid(),
      channel: z.string(),
      consent_type: z.string(),
      status: z.string(),
      source: z.string(),
      disclosure_version: z.string(),
      evidence_reference: z.string(),
      captured_at: z.string(),
      withdrawn_at: nullable,
    }),
  ),
  communications: z.array(
    z.object({
      id: z.uuid(),
      direction: z.string(),
      channel: z.string(),
      status: z.string(),
      message_reference: z.string(),
      provider_message_id: nullable,
      workflow_run_id: z.uuid(),
      workflow_status: nullable,
      sent_at: nullable,
      delivered_at: nullable,
      failed_at: nullable,
    }),
  ),
  submissions: z.array(
    z.object({
      id: z.uuid(),
      source_id: z.uuid(),
      external_submission_id: z.string(),
      received_at: z.string(),
      status: z.string(),
    }),
  ),
  states: z.array(
    z.object({
      id: z.uuid(),
      from_status: nullable,
      to_status: z.string(),
      actor_type: z.string(),
      safe_reason: nullable,
      created_at: z.string(),
    }),
  ),
  crm_mappings: z.array(
    z.object({
      id: z.uuid(),
      connection_id: z.uuid(),
      external_lead_id: z.string(),
      sync_status: z.string(),
    }),
  ),
  assignees: z.array(
    z.object({
      user_profile_id: z.uuid(),
      display_name: nullable,
      membership_status: z.enum([
        "active",
        "invited",
        "suspended",
        "revoked",
        "expired",
      ]),
      membership_type: z.enum(["internal", "client", "partner", "support"]),
      role_keys: z.array(z.string()),
    }),
  ),
  history: z.array(history),
  capabilities: z.object({
    can_assign: z.boolean(),
    can_respond: z.boolean(),
    can_manage_consent: z.boolean(),
    can_read_audit: z.boolean(),
    allowed_statuses: z.array(z.string()),
    can_record_outcome: z.boolean(),
  }),
  history_limit: z.literal(50),
  history_quality: z.literal("bounded_partial"),
  downstream_outcomes: downstream,
});
export type LeadsView = z.infer<typeof workspace>;
export type LeadDetailView = z.infer<typeof detail>;
export function adaptLeads(
  raw: unknown,
  org: string,
  location?: string,
): LeadsView {
  const view = workspace.parse(
    raw,
  ) satisfies components["schemas"]["LeadsWorkspace"];
  if (
    view.organization_id !== org ||
    (location && view.location_id !== location) ||
    (view.location_id &&
      !view.locations.some((l) => l.id === view.location_id)) ||
    view.items.some(
      (l) => view.location_id && l.location_id !== view.location_id,
    )
  )
    throw new Error("LEAD_SCOPE_MISMATCH");
  return view;
}
export function adaptLeadDetail(
  raw: unknown,
  org: string,
  id: string,
  location?: string,
): LeadDetailView {
  const view = detail.parse(
    raw,
  ) satisfies components["schemas"]["LeadWorkspaceDetail"];
  if (
    view.organization_id !== org ||
    view.lead.id !== id ||
    (location && view.lead.location_id !== location) ||
    view.source.id !== view.lead.source_id ||
    view.submissions.some((s) => s.source_id !== view.lead.source_id)
  )
    throw new Error("LEAD_SCOPE_MISMATCH");
  return view;
}
export const leadMetric = (value: number | null) =>
  value === null ? "Unavailable" : String(value);
export const outcomeLabel = (value: LeadDetailView["lead"]["outcome"]) =>
  ({
    recorded_conversion: "Recorded lead conversion",
    recorded_loss: "Recorded loss",
    unknown: "Unknown outcome",
  })[value];
