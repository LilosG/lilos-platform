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


test("SEO Search performance stays in flow ahead of SEO work", async ({ page }) => {
  await open(page, "/seo");
  const workspace = page.locator(
    "#tab-search-console > .seo-search-console-workspace",
  );
  await expect(workspace).toBeVisible();
  await expect(page.locator("#tab-overview")).toBeHidden();
  await expect(page.locator("#tab-crawl")).toBeHidden();
  await expect(page.locator("#tab-opportunities")).toBeHidden();

  await expect
    .poll(async () => {
      const searchBox = await workspace.boundingBox();
      const workBox = await page.locator("#seo-metrics").boundingBox();
      if (!searchBox || !workBox) return false;
      return searchBox.y + searchBox.height <= workBox.y + 1;
    })
    .toBe(true);
});

test("Automations domains are compact until the user expands one", async ({
  page,
}) => {
  await open(page, "/automations");
  const domains = page.locator(".ui-product-domain");
  await expect(domains.first()).toBeVisible();
  await expect(page.locator(".ui-product-domain[open]")).toHaveCount(0);
  const first = domains.first();
  await expect(first).not.toHaveAttribute("open", "");
  await first.locator("summary").click();
  await expect(first).toHaveAttribute("open", "");
});
