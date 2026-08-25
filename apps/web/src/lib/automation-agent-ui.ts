import type { AgentRunEvent, AgentRunSummary } from "./agents";
import type { WorkflowRunSummary } from "./workflows";

export type PendingAgentSelection = {
  skillKey: string;
  locationId: string;
  requestedAtMs: number;
};

const ACTIVE_AGENT_STATUSES = new Set([
  "queued",
  "running",
  "waiting_approval",
  "stopping",
]);

const FAILURE_WORKFLOW_STATUSES = new Set([
  "failed",
  "dead_lettered",
  "escalated",
]);

function timestamp(value: string | null): number {
  if (!value) return 0;
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

export function agentRunIsActive(run: AgentRunSummary): boolean {
  return ACTIVE_AGENT_STATUSES.has(run.status);
}

export function selectPendingAgentRun(
  runs: AgentRunSummary[],
  pending: PendingAgentSelection,
): AgentRunSummary | null {
  const earliestAccepted = pending.requestedAtMs - 5_000;
  const candidates = runs.filter((run) => {
    const created = timestamp(run.created_at ?? run.started_at);
    return (
      run.skill_key === pending.skillKey &&
      run.location_id === pending.locationId &&
      created >= earliestAccepted
    );
  });
  candidates.sort(
    (left, right) =>
      timestamp(right.created_at ?? right.started_at) -
      timestamp(left.created_at ?? left.started_at),
  );
  return candidates[0] ?? null;
}

export function actionableWorkflowFailureCount(
  runs: WorkflowRunSummary[],
): number {
  const latestByScope = new Map<string, WorkflowRunSummary>();
  for (const run of runs) {
    const workflowIdentity = run.workflow_key ?? run.workflow_name ?? run.id;
    const key = `${workflowIdentity}:${run.location_id ?? "organization"}`;
    const current = latestByScope.get(key);
    if (
      !current ||
      timestamp(run.created_at) > timestamp(current.created_at)
    ) {
      latestByScope.set(key, run);
    }
  }
  return [...latestByScope.values()].filter((run) =>
    FAILURE_WORKFLOW_STATUSES.has(run.status),
  ).length;
}

export type AgentEventPresentation = {
  label: string;
  outcome: "success" | "warning" | "danger" | "neutral";
};

function toolName(event: AgentRunEvent): string {
  const value = event.event_document.tool;
  return typeof value === "string" && value ? value : "tool";
}

export function presentAgentEvent(
  event: AgentRunEvent,
): AgentEventPresentation {
  if (event.event_type === "tool.started") {
    return { label: `Started ${toolName(event)}`, outcome: "neutral" };
  }
  if (event.event_type === "tool.completed") {
    if (event.event_document.error === true) {
      return { label: `${toolName(event)} returned an error`, outcome: "danger" };
    }
    return { label: `Completed ${toolName(event)}`, outcome: "success" };
  }
  if (event.event_type === "approval.request") {
    return { label: "Approval requested", outcome: "warning" };
  }
  if (event.event_type === "approval.responded") {
    return { label: "Approval response accepted", outcome: "success" };
  }
  if (event.event_type === "run.completed") {
    return { label: "Hermes run completed", outcome: "success" };
  }
  if (event.event_type === "run.failed") {
    return { label: "Hermes run failed", outcome: "danger" };
  }
  if (event.event_type === "run.cancelled") {
    return { label: "Hermes run cancelled", outcome: "warning" };
  }
  return { label: event.event_type, outcome: "neutral" };
}
