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
  { path: "/insights", heading: "This deployment is not configured" },
  { path: "/administration", heading: "This deployment is not configured" },
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
