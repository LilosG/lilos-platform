import { describe, expect, it } from "vitest";

import type { AgentRunEvent, AgentRunSummary } from "./agents";
import {
  actionableWorkflowFailureCount,
  presentAgentEvent,
  selectPendingAgentRun,
} from "./automation-agent-ui";
import type { WorkflowRunSummary } from "./workflows";

function agentRun(overrides: Partial<AgentRunSummary> = {}): AgentRunSummary {
  return {
    id: "run-1",
    location_id: "location-1",
    skill_key: "seo.operator",
    status: "running",
    model: "hermes-agent",
    safe_error_code: null,
    started_at: "2026-08-25T17:20:00.000Z",
    completed_at: null,
    created_at: "2026-08-25T17:20:00.000Z",
    ...overrides,
  };
}

function workflowRun(
  overrides: Partial<WorkflowRunSummary> = {},
): WorkflowRunSummary {
  return {
    id: "workflow-1",
    workflow_key: "agent.seo",
    workflow_name: "Hermes SEO agent",
    product_key: "seo",
    status: "completed",
    trigger_type: "api",
    location_id: "location-1",
    input_document: {},
    output_reference: null,
    failure_code: null,
    correlation_id: "correlation-1",
    started_at: "2026-08-25T17:20:00.000Z",
    completed_at: "2026-08-25T17:20:05.000Z",
    created_at: "2026-08-25T17:20:00.000Z",
    job_status: "completed",
    job_attempt_count: 1,
    job_max_attempts: 3,
    job_last_error_category: null,
    ...overrides,
  };
}

describe("automation agent UI state", () => {
  it("selects the newly requested skill instead of a previously open run", () => {
    const selected = selectPendingAgentRun(
      [
        agentRun({
          id: "old-content",
          skill_key: "content.operator",
          created_at: "2026-08-25T17:19:00.000Z",
        }),
        agentRun({ id: "new-seo", skill_key: "seo.operator" }),
      ],
      {
        skillKey: "seo.operator",
        locationId: "location-1",
        requestedAtMs: Date.parse("2026-08-25T17:19:59.000Z"),
      },
    );

    expect(selected?.id).toBe("new-seo");
  });

  it("does not count superseded historical failures as current attention", () => {
    expect(
      actionableWorkflowFailureCount([
        workflowRun({
          id: "new-success",
          status: "completed",
          created_at: "2026-08-25T17:20:00.000Z",
        }),
        workflowRun({
          id: "old-failure",
          status: "failed",
          failure_code: "OLD_FAILURE",
          created_at: "2026-08-25T17:10:00.000Z",
        }),
        workflowRun({
          id: "reviews-failure",
          workflow_key: "agent.reviews",
          workflow_name: "Hermes reviews agent",
          status: "dead_lettered",
          failure_code: "CURRENT_FAILURE",
          created_at: "2026-08-25T17:21:00.000Z",
        }),
      ]),
    ).toBe(1);
  });

  it("presents tool errors clearly while keeping raw event data separate", () => {
    const event: AgentRunEvent = {
      sequence: 8,
      event_type: "tool.completed",
      event_document: { tool: "inspect_workflow", error: true },
      occurred_at: "2026-08-25T17:20:02.000Z",
    };

    expect(presentAgentEvent(event)).toEqual({
      label: "inspect_workflow returned an error",
      outcome: "danger",
    });
  });
});
