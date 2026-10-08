import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
const sim = "http://127.0.0.1:4455/test";
async function scenario(mode: string) {
  const response = await fetch(`${sim}/automations-scenario`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode }),
  });
  expect(response.ok).toBe(true);
}
async function login(page: Page, who: string, target: string) {
  await page.goto(`/login/?return=${encodeURIComponent(target)}`);
  await page.getByLabel("Email", { exact: true }).fill(`${who}@example.test`);
  await page.getByLabel("Password", { exact: true }).fill("synthetic-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.waitForURL((url) => !url.pathname.startsWith("/login"));
  await page.locator('body[data-app-ready="true"]').waitFor();
}
const clean = async (page: Page) =>
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
/** No ISO timestamp, enum value, cron string, identifier or API text in what a person reads. */
const noSystemText = async (page: Page) => {
  const text = await page.locator("main").innerText();
  expect(text).not.toMatch(
    /\b[A-Z]+(_[A-Z]+)+\b|\b[a-z]+(_[a-z]+)+\b|[0-9a-f]{8}-[0-9a-f]{4}-|\d{4}-\d{2}-\d{2}T|google_business_profile|\*\/\d+ \*|\d+ \d+ \* \* /,
  );
};
test.beforeEach(async () => scenario("default"));
test("overview: attention first, upcoming, recent outcomes and health counts", async ({
  page,
}) => {
  await login(page, "admin", "/automations/");
  await expect(page.locator("h1")).toHaveText("Automations");
  const strip = page.locator(".attentionstrip");
  await expect(strip.locator("[data-automation-attention-count]")).toHaveText(
    "3",
  );
  await expect(strip.locator(".listrow")).toHaveCount(3);
  await expect(strip).toContainText(
    "Google would not let LILOs read this profile.",
  );
  await expect(strip.getByRole("link", { name: "Investigate" })).toHaveCount(3);
  // A rate limit, a paused schedule and a never-run schedule are not problems.
  await expect(strip).not.toContainText("limiting requests");
  await expect(page.locator(".operationalstrip")).toContainText(
    "Require attention",
  );
  await expect(page.locator(".operationalstrip div").nth(1)).toContainText("3");
  await expect(page.getByText("Upcoming runs")).toBeVisible();
  await expect(page.getByText("Recent outcomes")).toBeVisible();
  await noSystemText(page);
  await clean(page);
});
test("filters by status, client and type; only real types are offered", async ({
  page,
}) => {
  await login(page, "admin", "/automations/?view=all");
  await expect(page.locator("[data-automation-id]")).toHaveCount(9);
  const types = await page
    .getByLabel("Filter automation type")
    .locator("option")
    .allInnerTexts();
  expect(types).toContain("Review monitoring");
  expect(types).not.toContain("Local ranking scan");
  expect(types).not.toContain("Monthly client report");
  await page.getByLabel("Filter automations by status").selectOption("paused");
  await page.waitForURL(/status=paused/);
  await expect(page.locator("[data-automation-id]")).toHaveCount(1);
  await expect(page.locator("tbody")).toContainText("Paused");
  await page.getByRole("link", { name: "Reset filters" }).click();
  await page
    .getByLabel("Filter automations by client")
    .selectOption({ label: "Synthetic Beta" });
  await page.waitForURL(/organization_id=/);
  await expect(page.locator("[data-automation-id]")).toHaveCount(3);
  await page
    .getByLabel("Filter automation type")
    .selectOption("reviews.ingest");
  await page.waitForURL(/type=reviews.ingest/);
  await expect(page.locator("[data-automation-id]")).toHaveCount(1);
  // No match is a designed state with a way out.
  await page.getByLabel("Filter automations by status").selectOption("paused");
  await expect(
    page.getByRole("heading", { name: "No automations match these filters" }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Reset filters" }).last().click();
  await expect(page.locator("[data-automation-id]")).toHaveCount(9);
  await noSystemText(page);
});
test("the dashboard health link lands on the filtered view with the same count", async ({
  page,
}) => {
  await login(page, "admin", "/");
  await page
    .locator("section", { hasText: "Operational health" })
    .getByRole("link", { name: /Needs attention/ })
    .last()
    .click();
  await expect(page).toHaveURL(/\/automations\/\?status=needs_attention/);
  await expect(page.locator("[data-automation-attention-count]")).toHaveText(
    "3",
  );
});
test("dialog: human action, recovery action, history behind Details", async ({
  page,
}) => {
  await login(page, "admin", "/automations/");
  await page
    .locator(".attentionstrip .listrow", { hasText: "GBP performance" })
    .getByRole("link", { name: "Investigate" })
    .click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toContainText("GBP performance refresh");
  await expect(dialog).toContainText("Human action required");
  await expect(dialog).toContainText("Needs attention");
  await expect(dialog).toContainText("Daily · 6:15 AM");
  await expect(dialog).toContainText("Google Business Profile");
  await expect(
    dialog.getByRole("link", { name: "Reconnect Google Business Profile" }),
  ).toHaveAttribute("href", "/clients/synthetic-alpha/integrations/");
  await expect(dialog.getByRole("button", { name: "Run now" })).toBeEnabled();
  // Run history is behind Details.
  await expect(dialog.getByText("Recent runs")).toBeHidden();
  await dialog.getByRole("button", { name: "Details" }).click();
  await expect(
    page.getByRole("heading", { name: "Recent runs" }),
  ).toBeVisible();
  await page
    .locator("#automation-history")
    .getByRole("button", { name: "Close", exact: true })
    .click();
  await noSystemText(page);
  await clean(page);
  await page.keyboard.press("Escape");
  await expect(page).toHaveURL(/\/automations\/$/);
});
test("run now: one request, disabled while running, row refreshed; not offered where unsafe", async ({
  page,
}) => {
  await login(page, "admin", "/automations/?view=all");
  // A scheduled post generator publishes: no Run now.
  await page
    .locator("tr", { hasText: "Business Profile posts" })
    .getByRole("link", { name: "View run" })
    .click();
  await expect(page.getByRole("button", { name: "Run now" })).toHaveCount(0);
  await page.goBack();
  // A paused schedule has none either.
  await page
    .locator("tr", { hasText: "Business Profile sync" })
    .getByRole("link", { name: "View run" })
    .click();
  await expect(page.getByRole("button", { name: "Run now" })).toHaveCount(0);
  await page.goBack();
  await page
    .locator("tr", { hasText: "Review monitoring" })
    .first()
    .getByRole("link", { name: "View run" })
    .click();
  const run = page.getByRole("button", { name: "Run now" });
  await run.dblclick();
  await expect(page.getByRole("button", { name: "Running…" })).toBeDisabled();
  await expect(page.getByRole("dialog")).toContainText("Running");
  const runs = await (await fetch(`${sim}/automations-runs`)).json();
  expect(runs.runs).toHaveLength(1);
  await page.goto("/automations/?view=all");
  await expect(
    page.locator("tr", { hasText: "Review monitoring" }).first(),
  ).toContainText("Running");
});
test("run now already running: typed message and a next step", async ({
  page,
}) => {
  await scenario("busy");
  await login(page, "a", "/clients/synthetic-alpha/automations/");
  await page
    .locator(".attentionstrip .listrow", { hasText: "GBP performance" })
    .getByRole("link", { name: "Investigate" })
    .click();
  await page.getByRole("button", { name: "Run now" }).click();
  const banner = page
    .getByRole("alert")
    .filter({ hasText: "Run did not start" });
  await expect(banner).toContainText("already running");
  await expect(
    banner.getByRole("link", { name: "Refresh status" }),
  ).toBeVisible();
  await noSystemText(page);
});
test("client view is scoped to one client and has no client filter", async ({
  page,
}) => {
  await login(page, "a", "/clients/synthetic-alpha/automations/?view=all");
  await expect(page.locator("[data-automation-id]")).toHaveCount(5);
  await expect(page.locator("main")).not.toContainText("Synthetic Beta");
  await expect(page.getByLabel("Filter automations by client")).toHaveCount(0);
  await expect(page.locator("main")).toContainText("Not run yet");
  await expect(page.locator("main")).toContainText("Every 6 hours");
  await noSystemText(page);
  await clean(page);
});
test("empty and error states are designed", async ({ page }) => {
  await scenario("empty");
  await login(page, "a", "/clients/synthetic-alpha/automations/");
  await expect(
    page.getByRole("heading", {
      name: "Nothing is scheduled for Synthetic Alpha",
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Open Integrations" }),
  ).toBeVisible();
  await page.goto("/automations/");
  await expect(
    page.getByRole("heading", { name: "No automations are scheduled yet" }),
  ).toBeVisible();
  await scenario("error");
  await page.goto("/automations/");
  await expect(
    page.getByRole("heading", {
      name: "Automations are temporarily unavailable",
    }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: "Try again" })).toBeVisible();
  await expect(page.locator("main")).not.toContainText("503");
  await page.goto("/clients/synthetic-alpha/automations/");
  await expect(
    page.getByRole("heading", {
      name: "Automations are temporarily unavailable",
    }),
  ).toBeVisible();
  await clean(page);
});
test("unknown filters and schedules are refused", async ({ page }) => {
  await login(page, "admin", "/");
  expect((await page.goto("/automations/?status=bogus"))?.status()).toBe(400);
  expect((await page.goto("/automations/not-a-schedule/"))?.status()).toBe(404);
});
