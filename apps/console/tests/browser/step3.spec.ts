import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
async function login(page: Page, email = "a@example.test", target = "/") {
  await page.goto(`/login/?return=${encodeURIComponent(target)}`);
  await page.getByLabel("Email", { exact: true }).fill(email);
  await page.getByLabel("Password", { exact: true }).fill("synthetic-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
}
const clean = async (page: Page) =>
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
const seoId = "33333333-3333-4333-8333-333333333333";
const growthId = "77777777-7777-4777-8777-777777777778";
const contentId = "77777777-7777-4777-8777-777777777779";
const rows = (page: Page) => page.locator("tr[data-opportunity-row]");
async function openNav(page: Page) {
  if (test.info().project.name === "mobile")
    await page.getByRole("button", { name: "Toggle navigation" }).click();
}
test("Portfolio Opportunities lists every kind on real data and filters on the server", async ({
  page,
}) => {
  await login(page);
  await openNav(page);
  await page
    .getByRole("navigation", { name: "Portfolio", exact: true })
    .getByRole("link", { name: /Opportunities/ })
    .click();
  await expect(page).toHaveURL(/\/opportunities\/$/);
  await expect(
    page.getByRole("heading", { name: "Opportunities", exact: true }),
  ).toBeVisible();
  await expect(page.locator("[data-not-built]")).toHaveCount(0);
  await expect(page.locator("body")).not.toContainText("not built yet");
  await expect(rows(page)).toHaveCount(3);
  await expect(rows(page).nth(0)).toContainText("Missing meta description");
  await expect(rows(page).nth(0)).toContainText("Synthetic Alpha");
  await expect(rows(page).nth(0)).toContainText("High");
  await expect(rows(page).nth(1)).toContainText("Win brunch searches");
  await expect(rows(page).nth(1)).toContainText("Growth plan");
  await expect(rows(page).nth(2)).toContainText("/blog/brunch");
  await expect(rows(page).nth(2)).toContainText("12 clicks");
  await expect(page.locator("[data-opportunity-count]")).toHaveText(
    "3 opportunities",
  );
  await clean(page);
  await page.getByLabel("Filter opportunity type").selectOption("growth");
  await expect(page).toHaveURL(/kind=growth/);
  await expect(rows(page)).toHaveCount(1);
  await expect(rows(page).first()).toContainText("Win brunch searches");
  await page.getByLabel("Filter opportunity type").selectOption("");
  await page.getByLabel("Filter priority").selectOption("medium");
  await expect(rows(page)).toHaveCount(2);
  await page.goto("/opportunities/?kind=nonsense");
  await expect(page.locator("body")).toContainText("Invalid filter");
});
test("Client Opportunities tab replaces the not-built state and opens each kind's detail", async ({
  page,
}) => {
  await login(page, "a@example.test", "/clients/synthetic-alpha/");
  await openNav(page);
  await page
    .getByRole("navigation", { name: "Client operations" })
    .getByRole("link", { name: /Opportunities/ })
    .click();
  await expect(page).toHaveURL(/synthetic-alpha\/opportunities\/$/);
  await expect(page.locator("body")).not.toContainText("not built yet");
  await expect(rows(page)).toHaveCount(3);
  // A client's own rows do not repeat the client filter.
  await expect(page.getByLabel("Filter opportunities by client")).toHaveCount(
    0,
  );
  await rows(page).nth(0).getByRole("link", { name: "Details" }).click();
  const dialog = page.getByRole("dialog");
  for (const heading of [
    "Why it was discovered",
    "Why it matters",
    "Supporting evidence",
    "Recommended next action",
    "Live check",
    "Status history",
  ])
    await expect(
      dialog.getByRole("heading", { name: heading, exact: true }),
    ).toBeVisible();
  await expect(dialog).toContainText("Missing meta description");
  await expect(dialog).toContainText("Persisted synthetic crawl finding");
  await expect(dialog).toContainText("Deterministic quality: passed");
  await expect(dialog.getByText("meta_description").first()).toBeVisible();
  await expect(dialog.getByText("No change has been published")).toBeVisible();
  await expect(
    dialog.getByRole("link", { name: "Open source area" }),
  ).toBeVisible();
  await clean(page);
  await page.goto(`/clients/synthetic-alpha/opportunities/${growthId}/`);
  await expect(
    page.getByRole("heading", { name: "Win brunch searches" }),
  ).toBeVisible();
  await expect(
    page.getByText("Demand exists for brunch queries"),
  ).toBeVisible();
  await expect(page.getByText("Confidence: 80%")).toBeVisible();
  await expect(page.locator("[data-growth-plan] li")).toHaveCount(1);
  await expect(
    page.getByRole("button", { name: "Approve growth plan" }),
  ).toBeDisabled();
  await page.goto(`/clients/synthetic-alpha/opportunities/${contentId}/`);
  await expect(page.getByText("Target: /blog/brunch")).toBeVisible();
  await expect(
    page.getByText("Status history is not available to your role."),
  ).toBeVisible();
});
test("A client without a site-change target keeps the opportunity, disabled with its typed reason", async ({
  page,
}) => {
  await login(page, "b@example.test", "/clients/synthetic-beta/opportunities/");
  await expect(rows(page)).toHaveCount(3);
  const seo = rows(page).nth(0);
  await expect(seo).toContainText("Missing meta description");
  await expect(
    seo.locator('[data-site-change-reason="SITE_CHANGES_NOT_CONFIGURED"]'),
  ).toHaveText("Site changes not configured for this client");
  await seo.getByRole("link", { name: "Details" }).click();
  await expect(
    page.locator('[data-site-change-reason="SITE_CHANGES_NOT_CONFIGURED"]'),
  ).toHaveText("Site changes not configured for this client");
  await expect(
    page.getByRole("button", { name: "Approve exact revision 1" }),
  ).toBeDisabled();
  await clean(page);
});
test("Approving a growth plan goes through the step-up gate and the existing decision endpoint", async ({
  page,
}) => {
  const detail = `/clients/synthetic-alpha/opportunities/${growthId}/`;
  await login(page, "a@example.test", detail);
  await expect(
    page.getByRole("button", { name: "Approve growth plan" }),
  ).toBeDisabled();
  await page
    .getByRole("link", {
      name: "Verify authenticator to request approval access",
    })
    .click();
  await page.getByRole("button", { name: "Set up authenticator" }).click();
  await page.getByLabel("Authenticator code").fill("123456");
  await page.getByRole("button", { name: "Verify", exact: true }).click();
  await expect(page).toHaveURL(new RegExp(detail));
  const decision = page.waitForResponse(
    (response) =>
      response.url().includes(`/growth/${growthId}/decision/`) &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Approve growth plan" }).click();
  expect((await decision).status()).toBe(200);
  await expect(
    page.getByText("Approved", { exact: true }).first(),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Approve growth plan" }),
  ).toHaveCount(0);
  await page.screenshot({
    path: `test-results/step3-detail-${test.info().project.name}.png`,
    fullPage: true,
  });
});
test("Opportunities are tenant scoped and closed to forged writes", async ({
  browser,
}) => {
  const context = await browser.newContext({
    baseURL: "http://127.0.0.1:4346",
  });
  const page = await context.newPage();
  await login(page, "b@example.test");
  const foreign = await page.goto(
    `/clients/synthetic-alpha/opportunities/${seoId}/`,
  );
  expect(foreign?.status()).toBe(404);
  expect(await page.content()).not.toContain("Synthetic Alpha");
  const list = await context.request.get(
    "/api/command-center/opportunities/?organization_id=11111111-1111-4111-8111-111111111111",
  );
  expect(list.status()).toBe(404);
  const forged = await context.request.post(
    `/api/organizations/22222222-2222-4222-8222-222222222222/growth/${growthId}/decision/`,
    {
      headers: {
        origin: "https://evil.test",
        "Content-Type": "application/json",
      },
      data: { approve: true },
    },
  );
  expect(forged.status()).toBe(403);
  const unknown = await context.request.get(
    "/api/command-center/opportunities/?kind=other",
  );
  expect(unknown.status()).toBe(400);
  await context.close();
});
