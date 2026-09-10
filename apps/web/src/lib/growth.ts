import { apiGet, apiRequest, type ApiOutcome } from "./api-client";

export type GrowthAction = {
  id: string;
  action_key: string;
  product_key: string;
  action_type: string;
  target_reference: string;
  execution_mode: "workflow" | "manual" | "monitor";
  executor_workflow_key: string | null;
  dependency_keys: string[];
  evidence_references: string[];
  expected_result_hypothesis: string;
  verification_plan: Record<string, unknown>;
  risk: "low" | "medium" | "high";
  effort: "low" | "medium" | "high";
  approval_required: boolean;
  status: string;
  workflow_run_id: string | null;
  result_reference: string | null;
  safe_error_code: string | null;
  started_at: string | null;
  completed_at: string | null;
};

export type GrowthOutcome = {
  id: string;
  action_id: string;
  classification: "improved" | "unchanged" | "regressed" | "inconclusive";
  baseline: Record<string, unknown>;
  measurement: Record<string, unknown>;
  limitations: string[];
  observed_at: string;
};

export type GrowthInitiativeSummary = {
  id: string;
  location_id: string | null;
  objective: string;
  priority_score: number;
  confidence: number;
  status: string;
  created_at: string;
  approved_at: string | null;
  completed_at: string | null;
};

export type GrowthInitiative = GrowthInitiativeSummary & {
  planner_agent_run_id: string;
  rationale: string;
  source_references: string[];
  actions: GrowthAction[];
  outcomes: GrowthOutcome[];
};

export function fetchGrowthQueue(
  organizationId: string,
): Promise<ApiOutcome<GrowthInitiativeSummary[]>> {
  return apiGet(`/api/v1/organizations/${organizationId}/growth`);
}

export function fetchGrowthInitiative(
  organizationId: string,
  initiativeId: string,
): Promise<ApiOutcome<GrowthInitiative>> {
  return apiGet(`/api/v1/organizations/${organizationId}/growth/${initiativeId}`);
}

export function decideGrowthInitiative(
  organizationId: string,
  initiativeId: string,
  approve: boolean,
): Promise<ApiOutcome<GrowthInitiative>> {
  return apiRequest(
    `/api/v1/organizations/${organizationId}/growth/${initiativeId}/decision`,
    {
      method: "POST",
      body: { approve },
    },
  );
}

export function dispatchGrowthInitiative(
  organizationId: string,
  initiativeId: string,
): Promise<
  ApiOutcome<{ dispatched_action_ids: string[]; initiative: GrowthInitiative }>
> {
  return apiRequest(
    `/api/v1/organizations/${organizationId}/growth/${initiativeId}/dispatch`,
    {
      method: "POST",
    },
  );
}

export function reconcileGrowthInitiative(
  organizationId: string,
  initiativeId: string,
): Promise<ApiOutcome<GrowthInitiative>> {
  return apiRequest(
    `/api/v1/organizations/${organizationId}/growth/${initiativeId}/reconcile`,
    {
      method: "POST",
    },
  );
}
