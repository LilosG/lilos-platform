import { apiRequest, type ApiOutcome } from "./api-client";

export type AgentCapabilities = {
  available: boolean;
  reason_code: string | null;
  runtime_version?: string;
  runtime_release?: string;
  model?: string;
  features: Record<string, boolean>;
  runtime?: Record<string, unknown>;
  sanctioned_tools?: string[];
  missing_required?: string[];
};

export type AgentRunSummary = {
  id: string;
  location_id: string | null;
  skill_key: string;
  status: string;
  model: string | null;
  safe_error_code: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string | null;
};

export type AgentRunEvent = {
  sequence: number;
  event_type: string;
  event_document: Record<string, unknown>;
  occurred_at: string;
};

export type AgentRunDetail = AgentRunSummary & {
  workflow_run_id: string;
  ai_execution_id: string | null;
  hermes_run_id: string | null;
  hermes_session_id: string;
  audit_correlation_id: string;
  skill_version: number;
  provider: string;
  capabilities: AgentCapabilities;
  current_approval: Record<string, unknown> | null;
  source_references: string[];
  output_references: string[];
  final_output: { text?: string } | null;
  usage: {
    input_tokens: number | null;
    output_tokens: number | null;
    estimated_cost_microunits: number | null;
    latency_ms: number | null;
  };
  events: AgentRunEvent[];
};

export const AGENT_WORKFLOWS = [
  ["agent.gbp", "GBP agent"],
  ["agent.seo", "SEO agent"],
  ["agent.content", "Content agent"],
  ["agent.reviews", "Reviews agent"],
  ["agent.insights", "Cross-product Insights agent"],
] as const;

export const AGENT_SKILL_BY_WORKFLOW = {
  "agent.gbp": "gbp.operator",
  "agent.seo": "seo.operator",
  "agent.content": "content.operator",
  "agent.reviews": "reviews.operator",
  "agent.insights": "insights.cross_product",
} as const;

export function agentSkillForWorkflow(workflowKey: string): string | null {
  return (
    AGENT_SKILL_BY_WORKFLOW[
      workflowKey as keyof typeof AGENT_SKILL_BY_WORKFLOW
    ] ?? null
  );
}

export function agentLabelForSkill(skillKey: string): string {
  const workflow = AGENT_WORKFLOWS.find(
    ([workflowKey]) => AGENT_SKILL_BY_WORKFLOW[workflowKey] === skillKey,
  );
  return workflow?.[1] ?? skillKey;
}

export function canControlAgent(
  capabilities: AgentCapabilities,
  feature: "run_stop" | "run_steer" | "run_approval_response",
): boolean {
  return capabilities.available && capabilities.features[feature] === true;
}

export function agentCapabilities(
  organizationId: string,
): Promise<ApiOutcome<AgentCapabilities>> {
  return apiRequest(
    `/api/v1/organizations/${organizationId}/agents/capabilities`,
  );
}

export function listAgentRuns(
  organizationId: string,
  locationId?: string,
): Promise<ApiOutcome<AgentRunSummary[]>> {
  const params = new URLSearchParams({ limit: "50" });
  if (locationId) params.set("location_id", locationId);
  return apiRequest(
    `/api/v1/organizations/${organizationId}/agents/runs?${params.toString()}`,
  );
}

export function getAgentRun(
  organizationId: string,
  agentRunId: string,
): Promise<ApiOutcome<AgentRunDetail>> {
  return apiRequest(
    `/api/v1/organizations/${organizationId}/agents/runs/${encodeURIComponent(agentRunId)}`,
  );
}

export function startAgentRun(
  organizationId: string,
  workflowKey: string,
  input: {
    locationId: string;
    idempotencyKey: string;
    objective?: string;
    contextReference?: string;
  },
): Promise<
  ApiOutcome<{ workflow_run_id: string; status: string; skill_key: string }>
> {
  return apiRequest(
    `/api/v1/organizations/${organizationId}/agents/${encodeURIComponent(workflowKey)}/runs`,
    {
      method: "POST",
      body: {
        location_id: input.locationId,
        idempotency_key: input.idempotencyKey,
        objective: input.objective ?? null,
        context_reference: input.contextReference ?? null,
      },
    },
  );
}

export function stopAgentRun(
  organizationId: string,
  agentRunId: string,
): Promise<ApiOutcome<{ id: string; status: string }>> {
  return apiRequest(
    `/api/v1/organizations/${organizationId}/agents/runs/${encodeURIComponent(agentRunId)}/stop`,
    { method: "POST" },
  );
}

export function steerAgentRun(
  organizationId: string,
  agentRunId: string,
  text: string,
): Promise<ApiOutcome<{ id: string; status: string }>> {
  return apiRequest(
    `/api/v1/organizations/${organizationId}/agents/runs/${encodeURIComponent(agentRunId)}/steer`,
    { method: "POST", body: { text } },
  );
}

export function decideAgentApproval(
  organizationId: string,
  agentRunId: string,
  choice: "once" | "deny",
): Promise<ApiOutcome<{ id: string; status: string }>> {
  return apiRequest(
    `/api/v1/organizations/${organizationId}/agents/runs/${encodeURIComponent(agentRunId)}/approval`,
    { method: "POST", body: { choice } },
  );
}

export function resetAgentSession(
  organizationId: string,
  skillKey: string,
  locationId: string,
): Promise<
  ApiOutcome<{ skill_key: string; version: number; expires_at: string }>
> {
  return apiRequest(
    `/api/v1/organizations/${organizationId}/agents/sessions/reset`,
    {
      method: "POST",
      body: { skill_key: skillKey, location_id: locationId },
    },
  );
}
