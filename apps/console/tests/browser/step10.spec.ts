import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
const sim = "http://127.0.0.1:4455/test";
async function scenario(mode: string) {
  const response = await fetch(`${sim}/reports-scenario`, {
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
/** No ISO timestamp, enum value, identifier or API text in what a person reads. */
const noSystemText = async (page: Page) => {
  const text = await page.locator("main").innerText();
  expect(text).not.toMatch(
    /\b[A-Z]+(_[A-Z]+)+\b|\b[a-z]+(_[a-z]+)+\b|[0-9a-f]{8}-[0-9a-f]{4}-|\d{4}-\d{2}-\d{2}T/,
  );
};
test.beforeEach(async () => scenario("default"));
test("portfolio to client to report: generate, draft, approve and mark sent", async ({
  page,
}) => {
  await login(page, "admin", "/reports/");
  await expect(page.locator("h1")).toHaveText("Reports");
  await expect(page.getByText("Reports ready")).toBeVisible();
  await expect(page.locator("tbody tr")).toHaveCount(2);
  await expect(page.locator("tbody")).toContainText("Not generated");
  await noSystemText(page);
  await clean(page);

  await page
    .locator("tr", { hasText: "Synthetic Alpha" })
    .getByRole("link", { name: "Open reports" })
    .click();
  await expect(
    page.getByText("September report has not been generated"),
  ).toBeVisible();
  await expect(page.getByText("Upcoming reporting activity")).toBeVisible();
  await expect(page.locator("main")).toContainText("Nov 1, 8:00 AM Pacific");
  await clean(page);
  await page.getByRole("link", { name: "New report" }).first().click();
  await expect(page.getByRole("heading", { name: "New report" })).toBeVisible();
  await page.getByRole("button", { name: "Generate report" }).click();

  await page.waitForURL(/\/reports\/2026-09\/\?revision=1$/);
  await expect(page.locator("h1")).toHaveText(
    "September 2026 performance report",
  );
  await expect(
    page.getByText("Profile views", { exact: true }).first(),
  ).toBeVisible();
  await expect(page.getByText("Scorecard")).toBeVisible();
  await expect(page.getByRole("button", { name: "Approve" })).toBeDisabled();
  await noSystemText(page);
  await clean(page);

  await page.getByRole("button", { name: /^Details/ }).click();
  await expect(page.locator("#report-notes")).toContainText(
    "Covers September 2026, compared with the month before (August 2026).",
  );
  await page
    .locator("#report-notes")
    .getByRole("button", { name: "Close" })
    .last()
    .click();

  await page.getByRole("button", { name: "Draft with Hermes" }).click();
  await expect(page.locator("textarea[name=what_changed]")).toHaveValue(
    /1,800 times/,
  );
  await expect(page.getByRole("button", { name: "Approve" })).toBeEnabled();
  await page.getByRole("button", { name: "Approve" }).click();
  const dialog = page.locator("#report-confirm");
  await expect(dialog).toContainText("Synthetic Alpha · September 2026");
  await dialog.getByRole("button", { name: "Approve report" }).click();
  await page.waitForLoadState("load");
  await expect(page.locator("textarea")).toHaveCount(0);
  await expect(page.getByText("Ready to send").first()).toBeVisible();

  await page.getByLabel("Sent on").fill("2026-10-03");
  await page.getByRole("button", { name: "Mark as sent" }).click();
  await expect(page.locator("#report-confirm")).toContainText("Oct 3, 2026");
  await page
    .locator("#report-confirm")
    .getByRole("button", { name: "Record as sent" })
    .click();
  await expect(page.getByText("Sent Oct 3, 2026")).toBeVisible();

  await page.goto("/clients/synthetic-alpha/reports/");
  await expect(page.locator("tbody")).toContainText("Oct 3, 2026");
  await expect(page.locator("tbody")).toContainText("vs previous period");
  await page.getByRole("link", { name: "View report" }).click();
  await expect(page.locator("h1")).toHaveText(
    "September 2026 performance report",
  );
});
test("a failed read is a designed error, never sample data", async ({
  page,
}) => {
  await scenario("error");
  await login(page, "admin", "/reports/");
  await expect(
    page.getByText("Reports are temporarily unavailable"),
  ).toBeVisible();
});
