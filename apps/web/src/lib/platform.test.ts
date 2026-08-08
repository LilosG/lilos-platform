import { describe, expect, it } from "vitest";
import { navigation, readinessLabel, requiresStepUp } from "./platform";

describe("navigation", () => {
  it("is a static, always-rendered list independent of any client-held permission set", () => {
    expect(navigation.map((item) => item.key)).toEqual([
      "overview",
      "gbp",
      "reviews",
      "leads",
      "content",
      "seo",
      "insights",
      "settings",
      "integrations",
      "admin",
      "onboarding",
    ]);
  });

  it("only links to real routes: no hash-fragment placeholders", () => {
    for (const item of navigation) {
      expect(item.href.startsWith("#")).toBe(false);
      expect(item.href.startsWith("/")).toBe(true);
    }
  });
});

describe("readinessLabel", () => {
  it("maps the real backend readiness_state values to display labels", () => {
    expect(readinessLabel("ready")).toBe("ready");
    expect(readinessLabel("blocked")).toBe("blocked");
    expect(readinessLabel("not_entitled")).toBe("setup");
  });
});

describe("requiresStepUp", () => {
  it("requires verified aal2 for step-up actions", () => {
    expect(requiresStepUp("aal1", "aal2")).toBe(true);
    expect(requiresStepUp("aal2", "aal2")).toBe(false);
    expect(requiresStepUp("aal1", "aal1")).toBe(false);
  });
});
