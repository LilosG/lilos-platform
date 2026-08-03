import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test("workspace has no serious accessibility violations", async ({ page }) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Good morning, Alex." }),
  ).toBeVisible();
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

test("status and metrics remain semantic without color or fabricated zero", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.getByText("Not available", { exact: true })).toBeVisible();
  await page.getByText("View accessible data table", { exact: true }).click();
  await expect(
    page.getByRole("table", { name: "Organic clicks by week" }),
  ).toBeVisible();
  await expect(page.getByText("degraded", { exact: true })).toBeVisible();
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
