import {
  agentCapabilities,
  startAgentRun,
  type AgentCapabilities,
} from "./agents";
import type { ApiOutcome } from "./api-client";
import { fetchGBPLocations } from "./gbp";
import { fetchLocations, type LocationSummary } from "./workspace";
import { getWorkflowRun, type WorkflowRunDetail } from "./workflows";

export const PRODUCT_AGENT_WORKFLOWS = [
  "agent.growth",
  "agent.gbp",
  "agent.seo",
  "agent.content",
  "agent.reviews",
  "agent.insights",
] as const;

export type ProductAgentWorkflow = (typeof PRODUCT_AGENT_WORKFLOWS)[number];

export const PRODUCT_AGENT_LABELS: Record<ProductAgentWorkflow, string> = {
  "agent.growth": "Growth Planner",
  "agent.gbp": "GBP agent",
  "agent.seo": "SEO agent",
  "agent.content": "Content agent",
  "agent.reviews": "Reviews agent",
  "agent.insights": "Insights agent",
};

export const PRODUCT_AGENT_OBJECTIVES: Record<ProductAgentWorkflow, string> = {
  "agent.growth":
    "Synthesize current cross-product evidence into the highest-priority governed Growth initiative and action plan.",
  "agent.gbp":
    "Analyze the selected location's Business Profile evidence and prepare the highest-priority governed proposals.",
  "agent.seo":
    "Analyze current SEO evidence for the selected location and prioritize actionable opportunities without assuming new content is required.",
  "agent.content":
    "Analyze current governed content opportunities for the selected location and prepare justified content or optimization proposals.",
  "agent.reviews":
    "Analyze current review evidence for the selected location and prepare governed response or review-strategy proposals.",
  "agent.insights":
    "Analyze current cross-product performance evidence for the selected location and surface the most decision-relevant insights.",
};

export type AgentLocationResolution =
  | { kind: "selected"; location: LocationSummary }
  | { kind: "none" }
  | { kind: "ambiguous"; locations: LocationSummary[] };

export type ProductAgentStartResult =
  | {
      kind: "started";
      workflowRunId: string;
      locationId: string;
      status: string;
      skillKey: string;
    }
  | { kind: "runtime"; outcome: ApiOutcome<AgentCapabilities> }
  | { kind: "start"; outcome: Awaited<ReturnType<typeof startAgentRun>> };

export function isProductAgentWorkflow(
  value: string | null | undefined,
): value is ProductAgentWorkflow {
  return PRODUCT_AGENT_WORKFLOWS.includes(value as ProductAgentWorkflow);
}

export function productAgentWorkflowFromHref(
  href: string | null | undefined,
): ProductAgentWorkflow | null {
  if (!href) return null;
  const url = new URL(href, "https://lilos.local");
  if (url.pathname !== "/automations") return null;
  const workflow = url.searchParams.get("agent");
  return isProductAgentWorkflow(workflow) ? workflow : null;
}

export function resolveAgentLocation(
  locations: LocationSummary[],
  requestedLocationId?: string | null,
  eligibleLocationIds?: ReadonlySet<string>,
): AgentLocationResolution {
  const eligible = eligibleLocationIds
    ? locations.filter((location) => eligibleLocationIds.has(location.id))
    : locations.filter((location) => location.status === "active");

  if (requestedLocationId) {
    const requested = eligible.find(
      (location) => location.id === requestedLocationId,
    );
    if (requested) return { kind: "selected", location: requested };
  }
  if (eligible.length === 0) return { kind: "none" };
  if (eligible.length === 1) return { kind: "selected", location: eligible[0] };
  return { kind: "ambiguous", locations: eligible };
}

export async function fetchAgentLocationResolution(
  organizationId: string,
  workflow: ProductAgentWorkflow,
  requestedLocationId?: string | null,
): Promise<
  | { kind: "resolved"; resolution: AgentLocationResolution }
  | {
      kind: "error";
      outcome:
        | Awaited<ReturnType<typeof fetchLocations>>
        | Awaited<ReturnType<typeof fetchGBPLocations>>;
    }
> {
  const locationsOutcome = await fetchLocations(organizationId);
  if (locationsOutcome.kind !== "ok") {
    return { kind: "error", outcome: locationsOutcome };
  }

  if (workflow !== "agent.gbp") {
    return {
      kind: "resolved",
      resolution: resolveAgentLocation(
        locationsOutcome.data,
        requestedLocationId,
      ),
    };
  }

  const gbpLocationsOutcome = await fetchGBPLocations(organizationId);
  if (gbpLocationsOutcome.kind !== "ok") {
    return { kind: "error", outcome: gbpLocationsOutcome };
  }

  const confirmedMappedLocationIds = new Set(
    gbpLocationsOutcome.data
      .filter(
        (location) =>
          location.mapping_status === "confirmed" &&
          Boolean(location.location_id),
      )
      .map((location) => location.location_id as string),
  );

  return {
    kind: "resolved",
    resolution: resolveAgentLocation(
      locationsOutcome.data,
      requestedLocationId,
      confirmedMappedLocationIds,
    ),
  };
}

export async function startProductAgent(
  organizationId: string,
  workflow: ProductAgentWorkflow,
  locationId: string,
): Promise<ProductAgentStartResult> {
  const capabilities = await agentCapabilities(organizationId);
  if (capabilities.kind !== "ok" || !capabilities.data.available) {
    return { kind: "runtime", outcome: capabilities };
  }

  const requestedAt = Date.now();
  const result = await startAgentRun(organizationId, workflow, {
    locationId,
    idempotencyKey: `product-${workflow}-${organizationId}-${locationId}-${requestedAt}`,
    objective: PRODUCT_AGENT_OBJECTIVES[workflow],
  });
  if (result.kind !== "ok") return { kind: "start", outcome: result };

  return {
    kind: "started",
    workflowRunId: result.data.workflow_run_id,
    locationId,
    status: result.data.status,
    skillKey: result.data.skill_key,
  };
}

export function workflowRunIsTerminal(run: WorkflowRunDetail): boolean {
  return [
    "completed",
    "failed",
    "cancelled",
    "canceled",
    "dead_letter",
    "waiting_approval",
  ].includes(run.status);
}

export async function waitForProductAgentRun(
  organizationId: string,
  workflowRunId: string,
  options: { intervalMs?: number; maxPolls?: number } = {},
): Promise<ApiOutcome<WorkflowRunDetail>> {
  const intervalMs = options.intervalMs ?? 4000;
  const maxPolls = options.maxPolls ?? 150;
  let latest: ApiOutcome<WorkflowRunDetail> | null = null;

  for (let attempt = 0; attempt < maxPolls; attempt += 1) {
    latest = await getWorkflowRun(organizationId, workflowRunId);
    if (latest.kind !== "ok" || workflowRunIsTerminal(latest.data)) {
      return latest;
    }
    await new Promise((resolve) => window.setTimeout(resolve, intervalMs));
  }

  return (
    latest ?? {
      kind: "error",
      status: 408,
      code: "WORKFLOW_STATUS_TIMEOUT",
      message: "Timed out while waiting for the agent run status.",
      details: [],
    }
  );
}
