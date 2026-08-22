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
