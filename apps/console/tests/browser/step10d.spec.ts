import { mkdir } from "node:fs/promises";
import { test, expect, type Page } from "@playwright/test";
const sim = "http://127.0.0.1:4455/test";
const visual = new URL("../../visual/step-10d-report-fixes/", import.meta.url);
const reportUrl = "/clients/synthetic-alpha/reports/2026-07_2026-09/";
async function login(page: Page, target: string) {
  const shell = !target.includes("/document/");
  await page.goto(`/login/?return=${encodeURIComponent(target)}`);
  await page.getByLabel("Email", { exact: true }).fill("admin@example.test");
  await page.getByLabel("Password", { exact: true }).fill("synthetic-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.waitForURL((url) => !url.pathname.startsWith("/login"));
  if (shell) await page.locator('body[data-app-ready="true"]').waitFor();
}
test.beforeEach(async () => {
  const response = await fetch(`${sim}/reports-scenario`, {
    method: "POST",
    body: JSON.stringify({ mode: "averaged" }),
  });
  expect(response.ok).toBe(true);
  await mkdir(visual, { recursive: true });
});
const shot = (page: Page, name: string) =>
  page.screenshot({
    path: new URL(`${name}-${test.info().project.name}.png`, visual).pathname,
  });
test("the report page: row note under the label, search tile names June", async ({
  page,
}) => {
  await login(page, reportUrl);
  const row = page.locator("tbody th[scope=row]", { hasText: "Bookings" });
  const note = row.locator(".sub");
  await expect(note).toContainText("so this period's total is incomplete");
  expect(await note.evaluate((el) => getComputedStyle(el).display)).toBe(
    "block",
  );
  await expect(page.locator("main")).toContainText(
    "vs the monthly average of June 2026",
  );
  await row.scrollIntoViewIfNeeded();
  await shot(page, "report-page-scorecard");
});
test("the client document: charts leave out the first data month", async ({
  page,
}) => {
  await login(page, `${reportUrl}document/`);
  const score = page.locator('[data-section="scorecard"]');
  const bookings = score.locator("th[scope=row]", { hasText: "Bookings" });
  expect(
    await bookings
      .locator(".dsub.note")
      .evaluate((el) => getComputedStyle(el).display),
  ).toBe("block");
  await score.scrollIntoViewIfNeeded();
  await shot(page, "document-scorecard");
  const search = page.locator('[data-section="search"]');
  const chart = search.locator("figure.docchart").first();
  await expect(chart.locator(".key.excluded")).toHaveText(
    "Not used as a comparison",
  );
  await expect(chart.locator("rect.bar.excluded")).toHaveCount(1);
  await expect(chart.locator(".key.baseline")).toContainText(
    "Comparison average:",
  );
  await chart.scrollIntoViewIfNeeded();
  await shot(page, "document-search-chart");
  await expect(page.locator("ul.notelist, .notelist")).toContainText(
    "Search Console's comparison covers June 2026 only, so this compares monthly averages.",
  );
});
