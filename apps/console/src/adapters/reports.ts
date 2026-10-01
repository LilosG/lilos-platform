import { z } from "zod";
import type { components } from "@lilos/contracts/api";

const blocker = z.object({
  code: z.enum([
    "NO_METRICS", "INVALID_METRIC_REFERENCE", "METRIC_UNDEFINED",
    "DATA_MISSING", "DATA_STALE", "DATA_PARTIAL", "SOURCE_UNAVAILABLE",
    "DEFINITION_INACTIVE", "UNSUPPORTED_SCOPE",
  ]),
  metric_id: z.uuid().nullable(),
});
const report = z.object({
  id: z.uuid(),
  name: z.string(),
  definition_status: z.string(),
  readiness: z.enum(["ready", "not_ready"]),
  data_state: z.enum(["ready", "missing", "stale", "partial", "unavailable"]),
  blockers: z.array(blocker),
  metrics: z.array(z.object({
    metric_id: z.uuid(), name: z.string(), state: z.string(),
    source: z.string().nullable(), period_start: z.string().nullable(),
    period_end: z.string().nullable(), last_synced_at: z.string().nullable(),
  })),
  generation: z.enum(["queued", "generating", "ready", "sent", "failed", "unavailable"]),
  revision_id: z.uuid().nullable(),
  revision_status: z.string().nullable(),
  revision_created_at: z.string().nullable(),
  artifact_reference: z.string().nullable(),
  deliveries: z.array(z.object({
    id: z.uuid(), status: z.enum(["queued", "sent", "failed", "unavailable"]),
    created_at: z.string(), artifact_reference: z.string().nullable(),
  })),
});
const workspace = z.object({
  organization_id: z.uuid(),
  observed_at: z.string(),
  reports: z.array(report),
  schedule_state: z.literal("unavailable_no_canonical_report_schedule"),
  generation_state: z.literal("unavailable_no_canonical_report_workflow"),
  history_state: z.literal("bounded_partial"),
  source_state: z.literal("canonical_reports_and_metrics"),
});
export type ReportsView = z.infer<typeof workspace>;
type Transport = components["schemas"]["ReportsWorkspace"];
export function adaptReports(payload: unknown, organizationId: string): ReportsView {
  const data = workspace.parse(z.object({ data: workspace }).parse(payload).data);
  if (data.organization_id !== organizationId) throw new Error("Report scope mismatch");
  return data satisfies Transport;
}
