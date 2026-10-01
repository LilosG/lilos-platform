import { test, expect } from "@playwright/test";
import { clients } from "../../src/data/fixtures/clients";
import {
  routeInventory,
  route,
  localTabs,
  websiteTabs,
} from "../../src/config/routes";
import { opportunities } from "../../src/data/fixtures/opportunities";
const client = clients[0];
test("portfolio and client contexts use normal navigation", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await page.getByRole("link", { name: "Clients", exact: true }).click();
  await page
    .getByRole("link", { name: "Coco Maya", exact: true })
    .first()
    .click();
  await expect(page).toHaveURL(route("client", client.id));
  await expect(
    page.getByRole("heading", { name: "Coco Maya", exact: true }),
  ).toBeVisible();
  for (const area of [
    "Local Search",
    "Reviews",
    "Website & Content",
    "Leads",
    "Opportunities",
    "Automations",
    "Reports",
    "Integrations",
    "Settings",
  ]) {
    await page
      .locator("#sidebar")
      .getByRole("link", { name: area, exact: true })
      .click();
    await expect(page).toHaveURL(route("client", client.id, area));
    await expect(page.locator("main h1")).toHaveText(area);
  }
  await page
    .getByRole("link", { name: "‹ Entire Portfolio", exact: true })
    .click();
  await expect(page).toHaveURL("/");
  for (const area of [
    "Opportunities",
    "Reports",
    "Automations",
    "Integrations",
    "Administration",
    "Dashboard",
  ]) {
    await page
      .locator("#sidebar")
      .getByRole("link", { name: new RegExp("^" + area) })
      .click();
    await expect(page.locator("main h1")).toBeVisible();
  }
  expect(errors).toEqual([]);
});
test("every generated route renders without browser errors", async ({
  page,
}) => {
  test.setTimeout(240000);
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  // Include every fixture client and every workspace route, not only the complete fixture.
  for (const path of routeInventory) {
    const response = await page.goto(path, { waitUntil: "domcontentloaded" });
    expect(response?.status(), path).toBe(200);
    await expect(page.locator("main h1"), path).toBeVisible();
    await expect(page.locator("main")).not.toContainText("undefined");
  }
  expect(errors).toEqual([]);
});
for (const [area, tabs] of [
  ["Local Search", localTabs],
  ["Website & Content", websiteTabs],
] as const)
  test(`${area} tabs use real routes`, async ({ page }) => {
    await page.goto(route("client", client.id, area));
    for (const tab of tabs) {
      await page
        .locator("main nav.sectiontabs")
        .getByRole("link", { name: tab, exact: true })
        .click();
      await expect(page).toHaveURL(route("client", client.id, area, tab));
      await expect(
        page.locator('main nav.sectiontabs [aria-current="page"]'),
      ).toHaveText(tab);
    }
  });
test("canonical opportunity detail opens, closes, and returns keyboard focus", async ({
  page,
}) => {
  await page.goto("/opportunities/");
  const row = page.locator('[data-opportunity-id="13"]');
  const button = row.getByRole("button", { name: "Details", exact: true });
  await button.focus();
  await button.press("Enter");
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole("heading", { level: 2 })).toHaveText(
    opportunities.find((o) => o.id === 13)!.title,
  );
  await expect(dialog).toContainText("2,840");
  await expect(dialog).toContainText("Website conversion events");
  await page.keyboard.press("Escape");
  await expect(dialog).not.toBeVisible();
  await expect(button).toBeFocused();
  await button.press("Space");
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Close details" })
    .click();
  await expect(button).toBeFocused();
});
test("client opportunity rows open by pointer, Enter, and Space", async ({
  page,
}) => {
  await page.goto(route("client", client.id, "Opportunities"));
  const row = page.locator('[data-opportunity-id="13"]');
  const dialog = page.getByRole("dialog");
  const heading = dialog.getByRole("heading", { level: 2 });
  const expectedTitle = opportunities.find((o) => o.id === 13)!.title;

  await row.click({ position: { x: 20, y: 20 } });
  await expect(dialog).toBeVisible();
  await expect(heading).toHaveText(expectedTitle);
  await page.keyboard.press("Escape");
  await expect(dialog).not.toBeVisible();
  await expect(row).toBeFocused();

  await row.press("Enter");
  await expect(dialog).toBeVisible();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Close details" })
    .click();
  await expect(row).toBeFocused();

  await row.press("Space");
  await expect(dialog).toBeVisible();
  await expect(heading).toHaveText(expectedTitle);
});
for (const area of [
  "Overview",
  "Local Search",
  "Reviews",
  "Website & Content",
  "Leads",
  "Opportunities",
])
  test(`opportunity entry point in ${area}`, async ({ page }) => {
    await page.goto(route("client", client.id, area));
    const entry = page.locator('main [data-command="openOpp"]').first();
    await expect(entry).toBeVisible();
    const ids = JSON.parse(
      (await entry.getAttribute("data-args")) || "[]",
    ) as number[];
    await entry.click();
    await expect(
      page.getByRole("dialog").getByRole("heading", { level: 2 }),
    ).toHaveText(opportunities.find((o) => o.id === ids[0])!.title);
  });
test("opportunity filters and sample work status", async ({ page }) => {
  await page.goto(route("client", client.id, "Opportunities"));
  await page
    .getByLabel("Filter opportunity classification")
    .selectOption("Data & Tracking");
  await expect(page.locator("main [data-opportunity-id]:visible")).toHaveCount(
    1,
  );
  await page.locator('main [data-opportunity-id="19"] button').click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Start work", exact: true })
    .click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await page.reload();
  await page.locator('main [data-opportunity-id="19"] button').click();
  await expect(
    page.getByRole("dialog").getByRole("button", { name: "In progress" }),
  ).toBeDisabled();
});
