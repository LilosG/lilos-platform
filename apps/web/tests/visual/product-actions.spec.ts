import { expect, test } from "@playwright/test";

async function open(
  page: import("@playwright/test").Page,
  route: string,
): Promise<void> {
  await page.goto(
    `/evidence-session?next=${encodeURIComponent(route)}&mode=full`,
  );
  await page.waitForURL((url) => url.pathname === route);
}

test("Business Profile post creation starts inside Business Profile", async ({
  page,
}) => {
  await open(page, "/gbp");
  await expect(page.locator("#gbp-workspace")).toBeVisible();
  await page.getByRole("button", { name: "Create GBP post" }).click();
  await expect(page.locator("#tab-posts")).toBeVisible();
  await expect(page.locator("#post-content")).toBeFocused();
  await expect(
    page.locator("[data-product-automations='gbp'] .ui-automation-card"),
  ).not.toHaveCount(0);
});

test("SEO crawl starts inside SEO", async ({ page }) => {
  await open(page, "/seo");
  await page
    .getByRole("button", { name: "Run crawl", exact: true })
    .first()
    .click();
  await expect(page.locator("#tab-crawl")).toBeVisible();
  await expect(
    page
      .locator("#tab-crawl")
      .getByRole("button", { name: "Run crawl" })
      .first(),
  ).toBeVisible();
});

test("Content creation and review stay in Content", async ({ page }) => {
  await open(page, "/content");
  await page.getByRole("button", { name: "New content item" }).click();
  await expect(page.locator("#new-item-modal")).toBeVisible();
  await expect(
    page.locator("[data-product-automations='content'] .ui-automation-card"),
  ).not.toHaveCount(0);
});

test("Review inbox and sync stay in Reviews", async ({ page }) => {
  await open(page, "/reviews");
  await expect(page.locator("#reviews-list-panel")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Sync from Google" }),
  ).toBeVisible();
  await expect(
    page.locator("[data-product-automations='reviews'] .ui-automation-card"),
  ).not.toHaveCount(0);
});
