import { z } from "zod";
import type { components } from "@lilos/contracts/api";
const nullable = z.string().nullable();
const run = z.object({
  id: z.uuid(),
  workflow_key: z.string(),
  workflow_name: z.string(),
  location_id: z.uuid().nullable(),
  status: z.enum([
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
  ]),
  failure_code: nullable,
  created_at: z.string(),
  started_at: nullable,
  completed_at: nullable,
  correlation_id: z.string(),
  output_reference: nullable,
  attention: z
    .enum([
      "failure",
      "approval",
      "waiting",
      "retry",
      "partial",
      "stale",
      "reconciliation",
    ])
    .nullable(),
  outcome: z.enum([
    "execution_only",
    "recorded_result",
    "verified_publication",
    "unconfirmed_publication",
  ]),
  publication_status: nullable,
  publication_error: nullable,
  job_status: nullable,
  job_error_category: nullable,
  retry_at: nullable,
  agent_run_id: z.uuid().nullable(),
  agent_status: nullable,
  agent_error: nullable,
});
const workspace = z.object({
  organization_id: z.uuid(),
  location_id: z.uuid().nullable(),
  observed_at: z.string(),
  quality: z.literal("partial"),
  can_execute: z.boolean(),
  can_manage_schedules: z.boolean(),
  locations: z.array(z.object({ id: z.uuid(), name: z.string() })),
  schedules_state: z.enum(["available", "unavailable_permission"]),
  runtime_health: z.literal("unavailable_no_scoped_heartbeat"),
  definitions: z.array(
    z.object({
      key: z.string(),
      display_name: z.string(),
      product_key: z.string(),
      definition_status: z.string(),
      latest_version: z.number().int().nullable(),
      agent_eligible: z.boolean().nullable(),
      eligibility_reason: nullable,
    }),
  ),
  schedules: z.array(
    z.object({
      id: z.uuid(),
      key: z.string(),
      workflow_key: nullable,
      workflow_name: nullable,
      cron_expression: z.string(),
      timezone: z.string(),
      status: z.enum(["active", "paused", "cancelled"]),
      next_run_at: nullable,
      last_run_at: nullable,
      location_id: z.uuid().nullable(),
      overdue: z.boolean(),
      can_manage: z.boolean(),
    }),
  ),
  runs: z.array(run),
  attention: z.array(run),
  outcomes: z.array(run),
  total_runs: z.number().int().nonnegative(),
  next_offset: z.number().int().nullable(),
  attention_limit: z.literal(50),
  outcomes_limit: z.literal(10),
});
const detail = z.object({
  organization_id: z.uuid(),
  run,
  idempotency_key: z.string(),
  jobs: z.array(
    z.object({
      id: z.uuid(),
      status: z.string(),
      job_type: z.string(),
      attempt_count: z.number().int(),
      max_attempts: z.number().int(),
      available_at: z.string(),
      last_error_category: nullable,
      result_reference: nullable,
    }),
  ),
  attempts: z.array(
    z.object({
      id: z.uuid(),
      job_id: z.uuid(),
      attempt_number: z.number().int(),
      status: z.string(),
      started_at: z.string(),
      completed_at: nullable,
      error_category: nullable,
    }),
  ),
  history: z.array(
    z.object({
      id: z.uuid(),
      action: z.string(),
      result: z.string(),
      occurred_at: z.string(),
      correlation_id: nullable,
    }),
  ),
  history_state: z.enum(["bounded_partial", "unavailable_permission"]),
  can_stop: z.boolean(),
  can_steer: z.boolean(),
  can_respond_approval: z.boolean(),
  approval_request: nullable,
  recovery: z.literal("domain_controls_only"),
  quality: z.literal("bounded_partial"),
});
export type AutomationsView = z.infer<typeof workspace>;
export type AutomationRunView = z.infer<typeof run>;
export type AutomationDetailView = z.infer<typeof detail>;
export function adaptAutomations(
  raw: unknown,
  org: string,
  location?: string,
): AutomationsView {
  const view = workspace.parse(
    raw,
  ) satisfies components["schemas"]["AutomationWorkspace"];
  if (
    view.organization_id !== org ||
    view.location_id !== (location ?? null) ||
    [...view.runs, ...view.attention, ...view.outcomes, ...view.schedules].some(
      (r) => location && r.location_id !== location,
    )
  )
    throw new Error("AUTOMATION_SCOPE_MISMATCH");
  if (
    view.outcomes.some(
      (r) =>
        r.status !== "completed" ||
        r.attention ||
        !["recorded_result", "verified_publication"].includes(r.outcome),
    )
  )
    throw new Error("AUTOMATION_OUTCOME_MISMATCH");
  return view;
}
export function adaptAutomationDetail(
  raw: unknown,
  org: string,
  id: string,
): AutomationDetailView {
  const view = detail.parse(
    raw,
  ) satisfies components["schemas"]["AutomationDetail"];
  if (
    view.organization_id !== org ||
    view.run.id !== id ||
    view.attempts.some((a) => !view.jobs.some((j) => j.id === a.job_id))
  )
    throw new Error("AUTOMATION_SCOPE_MISMATCH");
  return view;
}
export const outcomeLabel = (value: AutomationRunView["outcome"]) =>
  ({
    execution_only: "Execution state only; result unconfirmed",
    recorded_result: "Recorded execution result; provider outcome unconfirmed",
    verified_publication: "Publication verified by canonical read-back",
    unconfirmed_publication: "Publication outcome unconfirmed",
  })[value];
export const when = (value: string | null) => value ?? "Unavailable";
