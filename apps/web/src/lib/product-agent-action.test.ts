import { describe, expect, it } from "vitest";

import {
  isProductAgentWorkflow,
  productAgentWorkflowFromHref,
  resolveAgentLocation,
  workflowRunIsTerminal,
} from "./product-agent-action";
import type { LocationSummary } from "./workspace";
import type { WorkflowRunDetail } from "./workflows";

const locations: LocationSummary[] = [
  { id: "loc-1", name: "Primary", status: "active", is_primary: true },
  { id: "loc-2", name: "Second", status: "active", is_primary: false },
];

describe("product agent actions", () => {
  it("recognizes every governed product agent workflow including Growth", () => {
    expect(isProductAgentWorkflow("agent.growth")).toBe(true);
    expect(isProductAgentWorkflow("agent.gbp")).toBe(true);
    expect(isProductAgentWorkflow("agent.seo")).toBe(true);
    expect(isProductAgentWorkflow("agent.content")).toBe(true);
    expect(isProductAgentWorkflow("agent.reviews")).toBe(true);
    expect(isProductAgentWorkflow("agent.insights")).toBe(true);
    expect(isProductAgentWorkflow("agent.unknown")).toBe(false);
  });

  it("converts legacy product-agent navigation targets into typed actions", () => {
    expect(
      productAgentWorkflowFromHref("/automations?agent=agent.growth"),
    ).toBe("agent.growth");
    expect(productAgentWorkflowFromHref("/automations?agent=agent.gbp")).toBe(
      "agent.gbp",
    );
    expect(productAgentWorkflowFromHref("/automations")).toBeNull();
    expect(productAgentWorkflowFromHref("/seo?agent=agent.seo")).toBeNull();
  });

  it("uses an explicitly selected active location", () => {
    expect(resolveAgentLocation(locations, "loc-2")).toEqual({
      kind: "selected",
      location: locations[1],
    });
  });

  it("requires an explicit choice when multiple active locations exist", () => {
    expect(resolveAgentLocation(locations)).toEqual({
      kind: "ambiguous",
      locations,
    });
  });

  it("auto-selects only when exactly one active location exists", () => {
    expect(resolveAgentLocation([locations[0]])).toEqual({
      kind: "selected",
      location: locations[0],
    });
  });

  it("allows a product-governed mapped location even before global activation", () => {
    const setupLocation: LocationSummary = {
      id: "loc-setup",
      name: "Mapped GBP location",
      status: "setup_required",
      is_primary: true,
    };
    expect(
      resolveAgentLocation(
        [setupLocation],
        "loc-setup",
        new Set(["loc-setup"]),
      ),
    ).toEqual({ kind: "selected", location: setupLocation });
  });

  it("does not treat an active but unmapped location as GBP-eligible", () => {
    expect(resolveAgentLocation(locations, null, new Set())).toEqual({
      kind: "none",
    });
  });

  it("treats approval waits as a polling handoff instead of spinning forever", () => {
    const run = {
      status: "waiting_approval",
    } as WorkflowRunDetail;
    expect(workflowRunIsTerminal(run)).toBe(true);
  });
});
