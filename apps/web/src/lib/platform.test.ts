import { describe, expect, it } from "vitest";

import { developmentPhase, platformName } from "./platform";

describe("platform identity", () => {
  it("identifies the Phase 0 development foundation", () => {
    expect(platformName).toBe("LILOs Platform");
    expect(developmentPhase).toBe("Roadmap Phase 0");
  });
});
