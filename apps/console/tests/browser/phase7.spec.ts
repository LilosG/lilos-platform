import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const base = "/clients/synthetic-alpha/reports/";
const scenario = "http://127.0.0.1:4457/test/reports-scenario";
async function login(page: import("@playwright/test").Page) {
  await page.goto(`/login/?return=${encodeURIComponent(base)}`);
  await page.getByLabel("Email", { exact: true }).fill("a@example.test");
  await page.getByLabel("Password", { exact: true }).fill("synthetic-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Report readiness" })).toBeVisible();
}
test.beforeEach(async ({ request }) => {
  await request.post(scenario, { data: { mode: "inventory" } });
});
test("Reports readiness, quality, history, generation and accessibility", async ({ page }) => {
  await login(page);
  await expect(page.getByText("Ready report")).toBeVisible();
  await expect(page.getByText(/Readiness: ready · Data: ready · Generation: sent/)).toBeVisible();
  await expect(page.getByText(/Readiness: not ready · Data: missing · Generation: queued/)).toBeVisible();
  await expect(page.getByText(/Data: stale · Generation: generating/)).toBeVisible();
  await expect(page.getByText(/Data: partial · Generation: failed/)).toBeVisible();
  await expect(page.getByText(/Data: unavailable · Generation: unavailable/)).toBeVisible();
  await expect(page.getByText(/no canonical report schedule exists/i)).toBeVisible();
  await page.getByText("Delivery history").first().click();
  await expect(page.getByText(/report:canonical-artifact/).last()).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.screenshot({ path: test.info().outputPath("reports.png"), fullPage: true });
});
test("Reports unavailable, tenant isolation, private cache and anonymous access", async ({ page, request }) => {
  await login(page);
  const response = await page.request.get(base);
  expect(response.headers()["cache-control"]).toContain("no-store");
  await request.post(scenario, { data: { mode: "empty" } });
  await page.reload();
  await expect(page.getByText(/No canonical report definitions/)).toBeVisible();
  await request.post(scenario, { data: { mode: "error" } });
  await page.reload();
  await expect(page.getByRole("alert")).toContainText("temporarily unavailable");
  await page.goto("/clients/synthetic-beta/reports/");
  await expect(page.getByRole("heading", { name: "Report readiness" })).toHaveCount(0);
  await page.context().clearCookies();
  await page.goto(base);
  await expect(page).toHaveURL(/\/login\//);
});
