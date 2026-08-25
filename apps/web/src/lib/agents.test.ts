import { describe, expect, it } from "vitest";

import {
  agentSkillForWorkflow,
  canControlAgent,
  type AgentCapabilities,
} from "./agents";

const available: AgentCapabilities = {
  available: true,
  reason_code: null,
  features: {
    run_stop: true,
    run_steer: true,
    run_approval_response: true,
  },
};

describe("Hermes capability-gated controls", () => {
  it("shows only positively advertised native controls", () => {
    expect(canControlAgent(available, "run_steer")).toBe(true);
    expect(
      canControlAgent(
        { ...available, features: { ...available.features, run_steer: false } },
        "run_steer",
      ),
    ).toBe(false);
  });

  it("fails closed when the runtime is degraded", () => {
    expect(
      canControlAgent(
        { ...available, available: false, reason_code: "HERMES_UNAVAILABLE" },
        "run_stop",
      ),
    ).toBe(false);
  });
});

describe("governed workflow skill mapping", () => {
  it("keeps SEO and Content on distinct governed skills", () => {
    expect(agentSkillForWorkflow("agent.seo")).toBe("seo.operator");
    expect(agentSkillForWorkflow("agent.content")).toBe("content.operator");
  });

  it("fails closed for unknown agent workflows", () => {
    expect(agentSkillForWorkflow("agent.unknown")).toBeNull();
  });
});
