import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { png } from "./photo";
async function login(page: Page, target: string) {
  await page.goto(`/login/?return=${encodeURIComponent(target)}`);
  await page.getByLabel("Email", { exact: true }).fill("b@example.test");
  await page.getByLabel("Password", { exact: true }).fill("synthetic-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.waitForURL((url) => !url.pathname.startsWith("/login"));
  await page.locator('body[data-app-ready="true"]').waitFor();
  if (target.includes("google-business-profile"))
    await page.locator("[data-gbp][data-ready]").waitFor();
}
const gbp = "/clients/synthetic-beta/local-search/google-business-profile/";
const clean = async (page: Page) =>
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
test.beforeEach(async ({ request }) => {
  await request.post("http://127.0.0.1:4455/test/gbp-reset", { data: {} });
});
test("Overview shows five tiles, momentum and the top ten queries", async ({
  page,
}) => {
  await login(page, "/clients/synthetic-beta/local-search/");
  await expect(page.locator(".metric")).toHaveCount(5);
  await expect(page.locator(".metrics")).toContainText("1,842");
  await expect(page.locator("[data-momentum]")).toContainText("Growing");
  await expect(page.locator(".tablewrap tbody tr")).toHaveCount(10);
  await expect(page.getByText("Recent syncs")).toBeHidden();
  await expect(page.getByText(/authorization/i)).toHaveCount(0);
  await page.getByRole("button", { name: /Data status/ }).click();
  await expect(page.getByRole("dialog")).toContainText("Search Console");
  await page.keyboard.press("Escape");
  await clean(page);
});
test("Search Console table sorts, searches and pages", async ({ page }) => {
  await login(page, "/clients/synthetic-beta/local-search/search-console/");
  const rows = page.locator("[data-query-rows] tr:not([hidden])");
  await expect(rows).toHaveCount(10);
  await page.getByRole("searchbox").fill("brunch");
  await expect(rows).toHaveCount(2);
  await page.getByRole("searchbox").fill("");
  await page.getByRole("button", { name: "Position" }).click();
  await expect(rows.first()).toContainText("cococabana san diego");
  await page.getByRole("button", { name: "Next" }).click();
  await expect(rows).toHaveCount(10);
  await expect(page.locator("[data-query-count]")).toContainText("11–20 of 20");
  await clean(page);
});
test("Rankings is a designed placeholder with no numbers", async ({ page }) => {
  await login(page, "/clients/synthetic-beta/local-search/rankings/");
  await expect(
    page.getByRole("heading", { name: "Local Visibility Grid is coming" }),
  ).toBeVisible();
  await expect(page.locator(".metric strong.muted")).toHaveCount(3);
  await clean(page);
});
test("Business Profile performance shows limits as '< 15' and switches location", async ({
  page,
}) => {
  await login(page, gbp);
  await expect(page.locator("main")).toContainText("< 15");
  await expect(page.locator("main")).toContainText("Google Maps");
  const before = await page.locator(".metric strong").first().innerText();
  await page.getByLabel("Business Profile location").selectOption({
    label: "Cococabana Kitchen",
  });
  await expect(page).toHaveURL(/location=/);
  expect(await page.locator(".metric strong").first().innerText()).not.toBe(
    before,
  );
  await clean(page);
});
test("Posts: create, approve and publish through the BFF", async ({ page }) => {
  await login(page, `${gbp}?view=posts`);
  await page.getByRole("button", { name: "New post", exact: true }).click();
  await page.getByLabel("Post copy").fill("Fresh oysters tonight");
  await page.getByRole("button", { name: "Save for approval" }).click();
  await expect(page.locator("[data-post-row]").first()).toContainText(
    "Fresh oysters tonight",
  );
  const approve = page.waitForRequest((r) => r.url().endsWith("/decision/"));
  await page.getByRole("button", { name: "Approve" }).first().click();
  expect((await approve).postDataJSON()).toEqual({ approve: true });
  await expect(page.locator(".badge", { hasText: /^Approved$/ })).toHaveCount(
    2,
  );
  await clean(page);
});
test("Photos, special hours and profile edits all go for approval", async ({
  page,
}) => {
  await login(page, `${gbp}?view=photos`);
  await page.getByRole("button", { name: "Add photo" }).first().click();
  await page.getByLabel("Photo", { exact: true }).setInputFiles({
    name: "new.png",
    mimeType: "image/png",
    buffer: png(300, 300),
  });
  await page.getByLabel("Who may use it").selectOption("Owned by the business");
  await page.getByRole("button", { name: "Upload for approval" }).click();
  await expect(page.locator("[data-photo]")).toHaveCount(5);
  await page.goto(`${gbp}?view=special-hours`);
  await page.locator("[data-gbp][data-ready]").waitFor();
  await page.getByRole("button", { name: "Add special hours" }).first().click();
  await page.getByLabel("Date", { exact: true }).fill("2026-12-31");
  await page.getByRole("button", { name: "Save for approval" }).click();
  await expect(page.locator("main")).toContainText(
    "Thursday, December 31, 2026",
  );
  await page.goto(`${gbp}?view=profile`);
  await page.locator("[data-gbp][data-ready]").waitFor();
  await expect(page.locator("main")).toContainText("Changes awaiting approval");
  await page.getByRole("button", { name: "Edit details" }).click();
  await page.getByLabel("New value").first().fill("A new description");
  await page.getByRole("button", { name: "Send for approval" }).click();
  await expect(page.locator("[data-change]")).toHaveCount(2);
  await clean(page);
});
