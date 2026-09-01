import { describe, expect, it } from "vitest";

import {
  blockerActionLabel,
  blockerHref,
  blockerStepKey,
  focusControl,
  isSamePage,
  pendingControlFromHash,
  resolveBlockers,
} from "./onboarding-blockers";
import type { BlockerResolution, OnboardingBlocker } from "./platform-admin";

function resolution(
  overrides: Partial<BlockerResolution> = {},
): BlockerResolution {
  return {
    step_key: null,
    route: "/onboarding",
    control: "business-facts",
    permission: "business_facts.approve",
    label: "Confirm the business details",
    ...overrides,
  };
}

function blocker(
  overrides: Partial<OnboardingBlocker> = {},
): OnboardingBlocker {
  return {
    message: "Confirm 3 business details.",
    product_name: null,
    resolution: resolution(),
    ...overrides,
  };
}

describe("resolveBlockers", () => {
  it("orders blockers by the order a client is actually set up in", () => {
    const ordered = resolveBlockers({
      blockers: [],
      blocker_details: [
        blocker({ resolution: resolution({ control: "business-facts" }) }),
        blocker({
          resolution: resolution({ control: "organization-profile" }),
        }),
        blocker({ resolution: resolution({ control: "website-domain" }) }),
        blocker({ resolution: resolution({ control: "locations" }) }),
      ],
    });

    expect(ordered.map((item) => item.resolution.control)).toEqual([
      "organization-profile",
      "locations",
      "website-domain",
      "business-facts",
    ]);
  });

  it("sorts an unrecognised control last rather than first", () => {
    const ordered = resolveBlockers({
      blockers: [],
      blocker_details: [
        blocker({ resolution: resolution({ control: "something-new" }) }),
        blocker({ resolution: resolution({ control: "locations" }) }),
      ],
    });

    expect(ordered.map((item) => item.resolution.control)).toEqual([
      "locations",
      "something-new",
    ]);
  });

  it("falls back to the sentence list when the API predates blocker_details", () => {
    // The deploy-skew window: Vercel is ahead of Render. The operator must
    // still see what is blocking them, even without a destination.
    const resolved = resolveBlockers({
      blockers: ["Select the client's industry."],
      blocker_details: undefined,
    });

    expect(resolved).toHaveLength(1);
    expect(resolved[0].message).toBe("Select the client's industry.");
    expect(resolved[0].resolution.route).toBe("/onboarding");
    expect(resolved[0].resolution.control).toBe("blockers");
    expect(resolved[0].resolution.label).toBe("Select the client's industry");
  });

  it("prefers blocker_details when both are present", () => {
    const resolved = resolveBlockers({
      blockers: ["stale sentence"],
      blocker_details: [blocker({ message: "current sentence" })],
    });

    expect(resolved.map((item) => item.message)).toEqual(["current sentence"]);
  });

  it("returns nothing when there is nothing blocking", () => {
    expect(resolveBlockers({ blockers: [], blocker_details: [] })).toEqual([]);
  });

  it("does not mutate the caller's array while sorting", () => {
    const details = [
      blocker({ resolution: resolution({ control: "business-facts" }) }),
      blocker({ resolution: resolution({ control: "locations" }) }),
    ];
    resolveBlockers({ blockers: [], blocker_details: details });

    expect(details[0].resolution.control).toBe("business-facts");
  });
});

describe("blockerHref", () => {
  it("keeps the selected client in the query string", () => {
    // Dropping ?org= would land the operator on a different client's setup.
    expect(blockerHref(resolution(), "org-123")).toBe(
      "/onboarding?org=org-123#business-facts",
    );
  });

  it("omits the query string when no client is selected", () => {
    expect(blockerHref(resolution(), null)).toBe("/onboarding#business-facts");
  });

  it("points at another route when the control lives elsewhere", () => {
    expect(
      blockerHref(
        resolution({ route: "/administration", control: "services" }),
        "org-123",
      ),
    ).toBe("/administration?org=org-123#services");
  });
});

describe("isSamePage", () => {
  it("recognises a blocker resolved on the current page", () => {
    expect(isSamePage(resolution(), "/onboarding")).toBe(true);
  });

  it("recognises a blocker that navigates away", () => {
    expect(
      isSamePage(resolution({ route: "/integrations" }), "/onboarding"),
    ).toBe(false);
  });
});

describe("labels and step keys", () => {
  it("uses the resolution label as the action text", () => {
    expect(blockerActionLabel(blocker())).toBe("Confirm the business details");
  });

  it("reports the step a blocker belongs to", () => {
    expect(
      blockerStepKey(
        blocker({ resolution: resolution({ step_key: "locations" }) }),
      ),
    ).toBe("locations");
  });

  it("reports no step for a blocker that is not one of the steps", () => {
    expect(blockerStepKey(blocker())).toBeNull();
  });
});

describe("pendingControlFromHash", () => {
  it("reads the control out of a fragment", () => {
    expect(pendingControlFromHash("#business-facts")).toBe("business-facts");
  });

  it("treats an empty fragment as no control", () => {
    expect(pendingControlFromHash("")).toBeNull();
    expect(pendingControlFromHash("#")).toBeNull();
    expect(pendingControlFromHash("#   ")).toBeNull();
  });
});

describe("focusControl", () => {
  it("finds a control by id and focuses it", () => {
    document.body.innerHTML = `<section id="business-facts">facts</section>`;
    const target = document.getElementById("business-facts")!;
    target.scrollIntoView = () => {};

    expect(focusControl(document, "business-facts")).toBe(true);
    expect(document.activeElement).toBe(target);
  });

  it("finds a control by data-control when there is no matching id", () => {
    document.body.innerHTML = `<div data-control="approval-policy">policy</div>`;
    const target = document.querySelector<HTMLElement>(
      '[data-control="approval-policy"]',
    )!;
    target.scrollIntoView = () => {};

    expect(focusControl(document, "approval-policy")).toBe(true);
    expect(document.activeElement).toBe(target);
  });

  it("reports failure rather than throwing when the control is absent", () => {
    document.body.innerHTML = "";
    expect(focusControl(document, "does-not-exist")).toBe(false);
  });

  it("removes the temporary tab stop once focus leaves", () => {
    // A section is not natively focusable, so focusing it needs tabindex. That
    // must not be left behind, or the section becomes a permanent tab stop.
    document.body.innerHTML = `<section id="locations">locations</section>`;
    const target = document.getElementById("locations")!;
    target.scrollIntoView = () => {};

    focusControl(document, "locations");
    expect(target.getAttribute("tabindex")).toBe("-1");

    target.dispatchEvent(new Event("blur"));
    expect(target.hasAttribute("tabindex")).toBe(false);
  });

  it("leaves an existing tabindex alone", () => {
    document.body.innerHTML = `<button id="activate" tabindex="0">Activate</button>`;
    const target = document.getElementById("activate")!;
    target.scrollIntoView = () => {};

    focusControl(document, "activate");
    expect(target.getAttribute("tabindex")).toBe("0");
  });
});
