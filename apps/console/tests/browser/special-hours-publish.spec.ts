import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

async function login(page: Page, target: string, who = "b") {
  await page.goto(`/login/?return=${encodeURIComponent(target)}`);
  await page.getByLabel("Email", { exact: true }).fill(`${who}@example.test`);
  await page.getByLabel("Password", { exact: true }).fill("synthetic-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.waitForURL((url) => !url.pathname.startsWith("/login"));
  await page.locator('body[data-app-ready="true"]').waitFor();
  await page.locator("[data-gbp][data-ready]").waitFor();
}
const hours =
  "/clients/synthetic-beta/local-search/google-business-profile/?view=special-hours";
const row = (page: Page, date: string) =>
  page.locator("[data-hours]").filter({ hasText: date });
test.beforeEach(async ({ request }) => {
  await request.post("http://127.0.0.1:4455/test/gbp-reset", { data: {} });
});
test("each special-hours date shows its publishing state as a chip", async ({
  page,
}) => {
  await login(page, hours);
  // A date a newer revision replaced is not listed.
  await expect(page.locator("[data-hours]")).toHaveCount(5);
  await expect(row(page, "November 26, 2026").locator(".badge")).toHaveText([
    "Awaiting approval",
  ]);
  const live = row(page, "December 25, 2026");
  await expect(live.locator(".badge")).toHaveText(["Closed", "Live on Google"]);
  await expect(live).toContainText("Confirmed on Google Oct 2, 2026");
  await expect(row(page, "December 28, 2026").locator(".badge")).toHaveText([
    "Publishing",
  ]);
  const failed = row(page, "January 1, 2027");
  await expect(failed.locator(".badge")).toHaveText(["Needs attention"]);
  await expect(failed).toContainText(
    "Editing is not turned on for this location. Turn it on in Integrations, then try again.",
  );
  await expect(failed.getByRole("button", { name: "Try again" })).toBeVisible();
  const unconfirmed = row(page, "January 2, 2027");
  await expect(unconfirmed.locator(".badge")).toHaveText(["Needs attention"]);
  await expect(unconfirmed).toContainText(
    "Try again to check and finish publishing",
  );
  // Nothing on the screen is a code, an id or a raw timestamp.
  const text = await page.locator("main").innerText();
  expect(text).not.toMatch(
    /\b[A-Z]+(_[A-Z]+)+\b|[0-9a-f]{8}-[0-9a-f]{4}-|\d{4}-\d{2}-\d{2}T|undefined|null|NaN/,
  );
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
});
test("Try again sends the date to Google once more and shows it publishing", async ({
  page,
}) => {
  await login(page, hours);
  const failed = row(page, "January 1, 2027");
  const request = page.waitForRequest(
    (r) =>
      r.method() === "POST" && /\/special-hours\/[^/]+\/retry\/$/.test(r.url()),
  );
  await failed.getByRole("button", { name: "Try again" }).click();
  expect((await request).postDataJSON()).toEqual({
    idempotency_key: expect.stringMatching(/^[0-9a-f-]{36}$/),
  });
  await page.locator("[data-gbp][data-ready]").waitFor();
  const after = row(page, "January 1, 2027");
  await expect(after.locator(".badge")).toHaveText(["Publishing"]);
  await expect(after.getByRole("button", { name: "Try again" })).toHaveCount(0);
});
