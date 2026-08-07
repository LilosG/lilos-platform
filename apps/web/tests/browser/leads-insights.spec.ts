import { expect, test } from "@playwright/test";

// These checks run against the unconfigured build (no PUBLIC_LILOS_* env), so
// the authenticated boot path never executes. They still guard the static
// markup and shell wiring that the Leads and Insights surfaces rely on, which
// previously shipped with dead/missing filter controls and an unwired
// organization switcher.

const LEAD_STATUS_FILTER_VALUES = [
  "",
  "new",
  "validating",
  "unassigned",
  "assigned",
  "acknowledged",
  "contact_attempted",
  "contacted",
  "qualifying",
  "qualified",
  "appointment_requested",
  "appointment_scheduled",
  "converted",
  "nurture",
  "unresponsive",
  "disqualified",
  "lost",
  "spam",
  "duplicate",
  "archived",
];

const LEAD_URGENCY_FILTER_VALUES = [
  "",
  "routine",
  "same_day",
  "urgent",
  "emergency",
  "unknown",
];

test.describe("Leads surface", () => {
  test("status filter offers every status the API contract permits, not just a partial set", async ({
    page,
  }) => {
    await page.goto("/leads");
    const values = await page
      .locator("#status-filter option")
      .evaluateAll((opts) => opts.map((o) => (o as HTMLOptionElement).value));
    expect(values).toEqual(LEAD_STATUS_FILTER_VALUES);
  });

  test("urgency filter includes the `unknown` default set at intake", async ({
    page,
  }) => {
    await page.goto("/leads");
    const values = await page
      .locator("#urgency-filter option")
      .evaluateAll((opts) => opts.map((o) => (o as HTMLOptionElement).value));
    expect(values).toEqual(LEAD_URGENCY_FILTER_VALUES);
  });

  test("detail section has a lifecycle facts container and a terminal-state note region", async ({
    page,
  }) => {
    await page.goto("/leads");
    await expect(page.locator("#lifecycle-facts")).toBeAttached();
    await expect(page.locator("#terminal-note")).toBeAttached();
    // The terminal note starts hidden until a terminal lead is opened.
    await expect(page.locator("#terminal-note")).toBeHidden();
  });

  test("renders the shared organization switcher from AppShell for multi-org context", async ({
    page,
  }) => {
    await page.goto("/leads");
    await expect(page.locator("#organization-switcher")).toBeAttached();
  });

  test("filter controls have accessible names", async ({ page }) => {
    // The controls live inside the hidden #leads-content region in the
    // unconfigured build, so visibility/focus cannot be asserted here; the
    // accessible naming is guarded via the aria-label attributes instead.
    await page.goto("/leads");
    await expect(page.locator("#status-filter")).toHaveAttribute(
      "aria-label",
      "Filter leads by status",
    );
    await expect(page.locator("#urgency-filter")).toHaveAttribute(
      "aria-label",
      "Filter leads by urgency",
    );
  });
});

test.describe("Insights surface", () => {
  test("renders the shared organization switcher from AppShell for multi-org context", async ({
    page,
  }) => {
    await page.goto("/insights");
    await expect(page.locator("#organization-switcher")).toBeAttached();
  });

  test("explains that it has no simulated data rather than presenting placeholder metrics as live", async ({
    page,
  }) => {
    await page.goto("/insights");
    // The explanatory copy is inside the hidden #insights-content region in
    // the unconfigured build, so it is asserted as attached markup rather
    // than visible.
    await expect(
      page.getByText("no simulated data", { exact: false }),
    ).toBeAttached();
    // No chart/bar placeholder markup should be present as live data.
    await expect(page.locator(".bars, .chart-card")).toHaveCount(0);
  });
});
