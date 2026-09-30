import { apiRequest, type ApiOutcome } from "./api-client";

export interface WorkflowTypeEntry {
  key: string;
  display_name: string;
  product_key: string;
  definition_status: string;
  latest_version: number | null;
}

export interface WorkflowScheduleEntry {
  id: string;
  key: string;
  workflow_key: string | null;
  workflow_name: string | null;
  cron_expression: string;
  timezone: string;
  status: "active" | "paused" | "cancelled";
  next_run_at: string | null;
  last_run_at: string | null;
  location_id: string | null;
  created_at: string | null;
}

export interface WorkflowRunSummary {
  id: string;
  workflow_key: string | null;
  workflow_name: string | null;
  product_key: string | null;
  status: string;
  trigger_type: string;
  location_id: string | null;
  input_document: Record<string, unknown>;
  output_reference: string | null;
  failure_code: string | null;
  correlation_id: string;
  started_at: string | null;
  completed_at: string | null;
  created_at: string | null;
  job_status: string | null;
  job_attempt_count: number | null;
  job_max_attempts: number | null;
  job_last_error_category: string | null;
}

export interface WorkflowRunDetail extends WorkflowRunSummary {
  jobs: Array<{
    id: string;
    job_type: string;
    status: string;
    attempt_count: number;
    max_attempts: number;
    last_error_category: string | null;
    result_reference: string | null;
    priority: number;
    lease_owner: string | null;
    available_at: string | null;
  }>;
  latest_attempts: Array<{
    attempt_number: number;
    status: string;
    worker_id: string;
    started_at: string | null;
    completed_at: string | null;
    error_category: string | null;
    safe_error: string | null;
  }>;
}

export type WorkflowRunStart = {
  workflow_run_id: string;
  status: string;
  product_key: string | null;
};

export function listWorkflowTypes(
  organizationId: string,
): Promise<ApiOutcome<WorkflowTypeEntry[]>> {
  return apiRequest(`/api/v1/organizations/${organizationId}/workflows`, {
    method: "GET",
  });
}

export function getWorkflowType(
  organizationId: string,
  workflowKey: string,
): Promise<ApiOutcome<WorkflowTypeEntry>> {
  return apiRequest(
    `/api/v1/organizations/${organizationId}/workflows/${encodeURIComponent(workflowKey)}`,
    { method: "GET" },
  );
}

export function listWorkflowRuns(
  organizationId: string,
  options?: {
    workflowKey?: string;
    locationId?: string;
    status?: string;
    limit?: number;
    offset?: number;
  },
): Promise<ApiOutcome<WorkflowRunSummary[]>> {
  const params = new URLSearchParams();
  if (options?.workflowKey) params.set("workflow_key", options.workflowKey);
  if (options?.locationId) params.set("location_id", options.locationId);
  if (options?.status) params.set("status", options.status);
  if (options?.limit) params.set("limit", String(options.limit));
  if (options?.offset) params.set("offset", String(options.offset));

  const qs = params.toString();
  return apiRequest(
    `/api/v1/organizations/${organizationId}/workflows/runs${qs ? `?${qs}` : ""}`,
    { method: "GET" },
  );
}

export function getWorkflowRun(
  organizationId: string,
  runId: string,
): Promise<ApiOutcome<WorkflowRunDetail>> {
  return apiRequest(
    `/api/v1/organizations/${organizationId}/workflows/runs/${encodeURIComponent(runId)}`,
    { method: "GET" },
  );
}

export function startWorkflowRun(
  organizationId: string,
  workflowKey: string,
  options: {
    locationId?: string;
    idempotencyKey: string;
    inputDocument?: Record<string, unknown>;
    execute?: boolean;
  },
): Promise<ApiOutcome<WorkflowRunStart>> {
  return apiRequest(
    `/api/v1/organizations/${organizationId}/workflows/${encodeURIComponent(workflowKey)}/runs`,
    {
      method: "POST",
      body: {
        location_id: options.locationId ?? null,
        idempotency_key: options.idempotencyKey,
        input_document: options.inputDocument ?? {},
        execute: options.execute ?? false,
      },
    },
  );
}

export function listSchedules(
  organizationId: string,
): Promise<ApiOutcome<WorkflowScheduleEntry[]>> {
  return apiRequest(
    `/api/v1/organizations/${organizationId}/workflows/schedules`,
    { method: "GET" },
  );
}

export function createSchedule(
  organizationId: string,
  options: {
    workflow_key: string;
    key: string;
    cron_expression: string;
    timezone: string;
    next_run_at: string;
    location_id?: string;
  },
): Promise<ApiOutcome<WorkflowScheduleEntry>> {
  return apiRequest(
    `/api/v1/organizations/${organizationId}/workflows/schedules`,
    {
      method: "POST",
      body: {
        workflow_key: options.workflow_key,
        key: options.key,
        cron_expression: options.cron_expression,
        timezone: options.timezone,
        next_run_at: options.next_run_at,
        location_id: options.location_id ?? null,
      },
    },
  );
}

export function updateSchedule(
  organizationId: string,
  scheduleId: string,
  options: {
    status?: string;
    cron_expression?: string;
    timezone?: string;
    next_run_at?: string;
  },
): Promise<ApiOutcome<WorkflowScheduleEntry>> {
  return apiRequest(
    `/api/v1/organizations/${organizationId}/workflows/schedules/${encodeURIComponent(scheduleId)}`,
    {
      method: "PATCH",
      body: {
        status: options.status ?? undefined,
        cron_expression: options.cron_expression ?? undefined,
        timezone: options.timezone ?? undefined,
        next_run_at: options.next_run_at ?? undefined,
      },
    },
  );
}

const TERMINAL_RUN_STATUSES = new Set([
  "completed",
  "partially_completed",
  "failed",
  "cancelled",
  "expired",
  "escalated",
]);

/**
 * Operator-facing copy for the typed codes a queued sync can end with. The
 * backend reports a code, never prose; this is the only place a code becomes a
 * sentence, and an unknown code falls back to a generic line that still shows it.
 */
const RUN_FAILURE_COPY: Record<string, string> = {
  INTEGRATION_RECONNECT_REQUIRED:
    "Google needs to be reconnected in Integrations before this can sync.",
  SEARCH_CONSOLE_SCOPE_REQUIRED:
    "Reconnect Google and grant Search Console access, then sync again.",
  ANALYTICS_SCOPE_REQUIRED:
    "Reconnect Google and grant Analytics access, then sync again.",
  SEARCH_CONSOLE_SYNC_INCOMPLETE:
    "Google did not return every report. Your previous data is unchanged; try again shortly.",
  ANALYTICS_SYNC_INCOMPLETE:
    "Google did not return every report. Your previous data is unchanged; try again shortly.",
  SEARCH_CONSOLE_SYNC_FAILED: "The sync failed. Try again shortly.",
  ANALYTICS_SYNC_FAILED: "The sync failed. Try again shortly.",
  SEARCH_PROPERTY_NOT_FOUND: "This property is no longer mapped.",
  ANALYTICS_PROPERTY_NOT_FOUND: "This property is no longer mapped.",
};

export function describeRunFailureCode(code: string | null): string {
  if (code && RUN_FAILURE_COPY[code]) return RUN_FAILURE_COPY[code];
  return code
    ? `The sync did not finish (${code}).`
    : "The sync did not finish.";
}

/**
 * Poll a queued workflow run until it reaches a terminal state.
 *
 * Resolves `ok` with the run when it completed, and otherwise an `error`
 * outcome, so callers render it with the same `describeFailure` path as any
 * other request: `WORKFLOW_RUN_FAILED` carries the run's typed failure code in
 * `details`, and `WORKFLOW_RUN_PENDING` means it is still working in the background.
 */
export async function waitForWorkflowRun(
  organizationId: string,
  runId: string,
  options: {
    intervalMs?: number;
    timeoutMs?: number;
    sleep?: (ms: number) => Promise<void>;
  } = {},
): Promise<ApiOutcome<WorkflowRunDetail>> {
  const intervalMs = options.intervalMs ?? 2_000;
  const timeoutMs = options.timeoutMs ?? 300_000;
  const sleep =
    options.sleep ?? ((ms: number) => new Promise((r) => setTimeout(r, ms)));
  let waited = 0;
  for (;;) {
    const outcome = await getWorkflowRun(organizationId, runId);
    if (outcome.kind !== "ok") return outcome;
    const run = outcome.data;
    if (TERMINAL_RUN_STATUSES.has(run.status)) {
      if (run.status === "completed" || run.status === "partially_completed") {
        return outcome;
      }
      return {
        kind: "error",
        status: 409,
        code: "WORKFLOW_RUN_FAILED",
        message: describeRunFailureCode(run.failure_code),
        details: [
          {
            code: run.failure_code ?? run.status,
            message: describeRunFailureCode(run.failure_code),
          },
        ],
      };
    }
    if (waited >= timeoutMs) {
      return {
        kind: "error",
        status: 202,
        code: "WORKFLOW_RUN_PENDING",
        message:
          "The sync is still running in the background. Reload in a few minutes to see the result.",
        details: [],
      };
    }
    await sleep(intervalMs);
    waited += intervalMs;
  }
}
