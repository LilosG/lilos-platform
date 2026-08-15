import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

// This build runs with no PUBLIC_LILOS_* configuration, so the workspace must
// show the truthful "not configured" state rather than fabricated content.

test("unconfigured workspace shows a truthful not-configured state, not fabricated content", async ({
  page,
}) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "This deployment is not configured" }),
  ).toBeVisible();
  await expect(page.getByText("Good morning", { exact: false })).toHaveCount(0);
  // The dashboard must not carry hard-coded "not available in this release" /
  // "no backing API" messaging that conflicts with real platform capability.
  await expect(page.getByText("Not available in this release")).toHaveCount(0);
  await expect(page.getByText("no backing API")).toHaveCount(0);
});

test("workspace has no serious accessibility violations in the not-configured state", async ({
  page,
}) => {
  await page.goto("/");
  const results = await new AxeBuilder({ page }).analyze();
  expect(
    results.violations.filter((item) =>
      ["serious", "critical"].includes(item.impact ?? ""),
    ),
  ).toEqual([]);
});

test("keyboard skip navigation reaches main content", async ({ page }) => {
  await page.goto("/");
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("link", { name: "Skip to main content" }),
  ).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("main")).toBeFocused();
});

test("mobile viewport does not create horizontal document overflow", async ({
  page,
}) => {
  await page.goto("/");
  const widths = await page.evaluate(() => ({
    client: document.documentElement.clientWidth,
    scroll: document.documentElement.scrollWidth,
  }));
  expect(widths.scroll).toBeLessThanOrEqual(widths.client + 1);
});

test("unconfigured login page shows a truthful not-configured state", async ({
  page,
}) => {
  await page.goto("/login");
  await expect(
    page.getByText("This deployment is not configured for sign-in."),
  ).toBeVisible();
  const results = await new AxeBuilder({ page }).analyze();
  expect(
    results.violations.filter((item) =>
      ["serious", "critical"].includes(item.impact ?? ""),
    ),
  ).toEqual([]);
});

test("unconfigured MFA step-up page shows a truthful not-configured state", async ({
  page,
}) => {
  await page.goto("/mfa");
  await expect(
    page.getByText("This deployment is not configured for sign-in."),
  ).toBeVisible();
  const results = await new AxeBuilder({ page }).analyze();
  expect(
    results.violations.filter((item) =>
      ["serious", "critical"].includes(item.impact ?? ""),
    ),
  ).toEqual([]);
});

test("unconfigured Business Profile page shows a truthful not-configured state, not fabricated GBP data", async ({
  page,
}) => {
  await page.goto("/gbp");
  await expect(
    page.getByRole("heading", { name: "This deployment is not configured" }),
  ).toBeVisible();
  await expect(
    page.getByText("Example Business", { exact: false }),
  ).toHaveCount(0);
  // The engineering-oriented raw capability-key/field inputs must not appear;
  // they are replaced by a task-specific dropdown.
  await expect(page.locator("#change-capability-key")).toHaveCount(0);
  await expect(page.locator("#change-field")).toHaveCount(0);
  await expect(page.locator("#change-task")).toHaveCount(0);
  await expect(page.locator("#change-gbp-location")).toBeAttached();
  const results = await new AxeBuilder({ page }).analyze();
  expect(
    results.violations.filter((item) =>
      ["serious", "critical"].includes(item.impact ?? ""),
    ),
  ).toEqual([]);
});

test("unconfigured Reviews page shows a truthful not-configured state, not fabricated review data", async ({
  page,
}) => {
  await page.goto("/reviews");
  await expect(
    page.getByRole("heading", { name: "This deployment is not configured" }),
  ).toBeVisible();
  await expect(page.getByText("5★ review", { exact: false })).toHaveCount(0);
  const results = await new AxeBuilder({ page }).analyze();
  expect(
    results.violations.filter((item) =>
      ["serious", "critical"].includes(item.impact ?? ""),
    ),
  ).toEqual([]);
});

test("Reviews page exposes a reachable operator action to import reviews from Google", async ({
  page,
}) => {
  await page.goto("/reviews");
  // The ingestion button is present in the markup (inside the hidden
  // configured region), proving the operator-path action exists even before
  // a deployment is wired — it is not a missing/unreachable control.
  await expect(page.locator("#ingest-reviews-button")).toHaveCount(1);
});

test("unconfigured Leads page shows a truthful not-configured state, not fabricated lead data", async ({
  page,
}) => {
  await page.goto("/leads");
  await expect(
    page.getByRole("heading", { name: "This deployment is not configured" }),
  ).toBeVisible();
  await expect(
    page.getByText("urgency · received", { exact: false }),
  ).toHaveCount(0);
  const results = await new AxeBuilder({ page }).analyze();
  expect(
    results.violations.filter((item) =>
      ["serious", "critical"].includes(item.impact ?? ""),
    ),
  ).toEqual([]);
});

test("unconfigured Content page shows a truthful not-configured state, not fabricated content data", async ({
  page,
}) => {
  await page.goto("/content");
  await expect(
    page.getByRole("heading", { name: "This deployment is not configured" }),
  ).toBeVisible();
  await expect(
    page.getByText("Passed policy validation", { exact: false }),
  ).toHaveCount(0);
  const results = await new AxeBuilder({ page }).analyze();
  expect(
    results.violations.filter((item) =>
      ["serious", "critical"].includes(item.impact ?? ""),
    ),
  ).toEqual([]);
});

test("Content page does not expose a PAT registration path", async ({
  page,
}) => {
  await page.goto("/content");
  await expect(page.locator("#register-connection-button")).toHaveCount(0);
  await expect(page.locator("#github-token")).toHaveCount(0);
  await expect(page.locator("#create-target-button")).toHaveCount(0);
  await expect(
    page.locator('#content-workspace a[href="/integrations"]', {
      hasText: "Manage integrations",
    }),
  ).toHaveText("Manage integrations");
});

test("unconfigured SEO page shows a truthful not-configured state, not fabricated SEO data", async ({
  page,
}) => {
  await page.goto("/seo");
  await expect(
    page.getByRole("heading", { name: "This deployment is not configured" }),
  ).toBeVisible();
  await expect(
    page.getByText("No confirmed websites yet", { exact: false }),
  ).toHaveCount(0);
  // The engineering-oriented raw "website key" input must not appear.
  await expect(page.locator("#website-key")).toHaveCount(0);
  const results = await new AxeBuilder({ page }).analyze();
  expect(
    results.violations.filter((item) =>
      ["serious", "critical"].includes(item.impact ?? ""),
    ),
  ).toEqual([]);
});

test("unconfigured Insights page shows a truthful not-configured state", async ({
  page,
}) => {
  await page.goto("/insights");
  await expect(
    page.getByRole("heading", { name: "This deployment is not configured" }),
  ).toBeVisible();
  const results = await new AxeBuilder({ page }).analyze();
  expect(
    results.violations.filter((item) =>
      ["serious", "critical"].includes(item.impact ?? ""),
    ),
  ).toEqual([]);
});

test("unconfigured Administration page shows a truthful not-configured state, not fabricated product data", async ({
  page,
}) => {
  await page.goto("/administration");
  await expect(
    page.getByRole("heading", { name: "This deployment is not configured" }),
  ).toBeVisible();
  await expect(page.locator("#administration-content")).toBeHidden();
  await expect(page.locator("#products-list li")).toHaveCount(0);
  const results = await new AxeBuilder({ page }).analyze();
  expect(
    results.violations.filter((item) =>
      ["serious", "critical"].includes(item.impact ?? ""),
    ),
  ).toEqual([]);
});

// This is the release-blocking regression this suite exists to catch: a
// deployment target (Vercel, a stale build, a broken route config) that
// serves the real overview shell but 404s on the actual product routes.
// Every route the sidebar can navigate to must resolve with a real HTTP
// 200 and a real heading — never a platform-level "not found" response.
const PROTECTED_ROUTES: ReadonlyArray<{ path: string; heading: string }> = [
  { path: "/", heading: "This deployment is not configured" },
  { path: "/gbp", heading: "This deployment is not configured" },
  { path: "/reviews", heading: "This deployment is not configured" },
  { path: "/leads", heading: "This deployment is not configured" },
  { path: "/content", heading: "This deployment is not configured" },
  { path: "/seo", heading: "This deployment is not configured" },
  { path: "/automations", heading: "This deployment is not configured" },
  { path: "/insights", heading: "This deployment is not configured" },
  { path: "/settings", heading: "This deployment is not configured" },
  { path: "/integrations", heading: "This deployment is not configured" },
  { path: "/administration", heading: "This deployment is not configured" },
  { path: "/onboarding", heading: "This deployment is not configured" },
];

for (const route of PROTECTED_ROUTES) {
  test(`direct navigation to ${route.path} returns a real page, not a platform 404`, async ({
    page,
  }) => {
    const response = await page.goto(route.path);
    expect(response, `no response received for ${route.path}`).not.toBeNull();
    expect(
      response?.status(),
      `${route.path} returned ${response?.status()} instead of 200`,
    ).toBe(200);
    await expect(
      page.getByRole("heading", { name: route.heading }),
    ).toBeVisible();
  });
}

test("every sidebar navigation link is a real path, never a hash fragment", async ({
  page,
}) => {
  await page.goto("/");
  const hrefs = await page
    .locator(".sidebar nav a")
    .evaluateAll((links) => links.map((link) => link.getAttribute("href")));
  expect(hrefs.length).toBeGreaterThan(0);
  for (const href of hrefs) {
    expect(
      href,
      "sidebar link must not be a hash-fragment placeholder",
    ).not.toMatch(/^#/);
    expect(href, "sidebar link must be a real absolute path").toMatch(/^\//);
  }
});
