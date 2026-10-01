import { test, expect } from "@playwright/test";
const base = "/clients/coco-maya";
test("client search, empty state, filters and sorting", async ({ page }) => {
  await page.goto("/clients/");
  await page.getByLabel("Search clients").fill("missing sample");
  await expect(page.locator("main [data-client-row]:visible")).toHaveCount(0);
  await expect(
    page.getByText("No clients match. Try another search or filter."),
  ).toBeVisible();
  await page.getByLabel("Search clients").fill("");
  await page.getByRole("button", { name: "Declining", exact: true }).click();
  await expect(page.locator("main [data-client-row]:visible")).toHaveCount(3);
  await page.getByRole("button", { name: "All clients", exact: true }).click();
  await page.getByLabel("Sort clients").selectOption("name");
  await expect(page.locator("main [data-client-row]").first()).toContainText(
    "Cedar Home Services",
  );
});
test("reporting period preserves source metrics and event rounding", async ({
  page,
}) => {
  await page.goto(base + "/leads/");
  await page.getByLabel("Reporting date range").selectOption("7");
  await expect(
    page.locator(".metrics .metric").nth(0).locator("strong"),
  ).toHaveText("36");
  await expect(
    page.locator(".metrics .metric").nth(1).locator("strong"),
  ).toHaveText("13");
  await expect(
    page.locator(".metrics .metric").nth(2).locator("strong"),
  ).toHaveText("29");
  await expect(page.locator("[data-period-components]")).toHaveText("78");
  await page.getByLabel("Reporting date range").selectOption("90");
  await expect(page.locator("[data-period-components]")).toHaveText("806");
  await page.locator('main [data-command="openOutcome"]').first().click();
  await expect(page.getByRole("dialog")).toContainText("372");
});
test("review draft, generation, publishing and requests", async ({ page }) => {
  await page.goto(base + "/reviews/");
  await page.locator('main [data-review-id="1-r1"] button').click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Generate response draft" })
    .click();
  await expect(page.getByRole("dialog").getByRole("textbox")).toHaveValue(
    /Thank you/,
  );
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Save draft", exact: true })
    .click();
  await expect(page.locator('main [data-review-id="1-r1"]')).toContainText(
    "Response draft",
  );
  await page.locator('main [data-review-id="1-r1"] button').click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Publish sample response", exact: true })
    .click();
  await expect(page.locator('main [data-review-id="1-r1"]')).toContainText(
    "Published response",
  );
  await page
    .getByRole("button", { name: "Review requests", exact: true })
    .first()
    .click();
  await expect(
    page.getByRole("heading", { name: "Review requests", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Create request", exact: true })
    .click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Stage sample request" })
    .click();
  await expect(page.locator('[data-field="requestCount"]')).toHaveText("1");
});
test("settings persist locally and optional approval behaves correctly", async ({
  page,
}) => {
  await page.goto(base + "/settings/");
  await page.getByLabel("Review response preference").selectOption("review");
  await page.getByRole("button", { name: "Save settings" }).click();
  await page
    .locator("#sidebar")
    .getByRole("link", { name: "Reviews", exact: true })
    .click();
  await page.locator('main [data-review-id="1-r1"] button').click();
  await page
    .getByRole("dialog")
    .getByRole("textbox")
    .fill("Thank you for visiting.");
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Publish sample response", exact: true })
    .click();
  await expect(page.locator('main [data-review-id="1-r1"]')).toContainText(
    "Awaiting approval",
  );
  await page
    .locator("#sidebar")
    .getByRole("link", { name: "Settings", exact: true })
    .click();
  await expect(page.getByLabel("Review response preference")).toHaveValue(
    "review",
  );
});
test("page repair unblocks website automation and inventory filters work", async ({
  page,
}) => {
  await page.goto(base + "/website-content/technical/");
  await page.getByRole("button", { name: "Inspect affected page" }).click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Fix sample links" })
    .click();
  await page
    .locator("#sidebar")
    .getByRole("link", { name: "Automations", exact: true })
    .click();
  await page
    .locator(`main [data-command="openAutomation"][data-args='["1-a3"]']`)
    .first()
    .click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Retry sample run" })
    .click();
  await expect(page.locator("#toast")).toContainText("Sample run completed");
  await page
    .getByRole("button", { name: "All automations", exact: true })
    .first()
    .click();
  await expect(page.locator("[data-automation-inventory]")).toBeVisible();
  await page.getByLabel("Filter automation type").selectOption("3");
  await expect(
    page.locator("[data-automation-inventory] [data-automation-id]:visible"),
  ).toHaveCount(1);
});
test("report summary downloads and fixed monthly measurements ignore period selector", async ({
  page,
}) => {
  await page.goto(base + "/reports/");
  await page.getByLabel("Reporting date range").selectOption("7");
  await page
    .getByRole("button", { name: "Open current report", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toContainText("4,110");
  const download = page.waitForEvent("download");
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Download summary" })
    .click();
  expect((await download).suggestedFilename()).toBe(
    "coco-maya-september-2026-report.txt",
  );
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Mark as sent", exact: true })
    .click();
  await expect(page.locator("main")).toContainText("Sent");
});
test("administration subviews and role preview", async ({ page }) => {
  await page.goto("/administration/");
  for (const [name, path] of [
    ["Onboarding", "onboarding"],
    ["Users", "users"],
    ["Platform / system", "platform"],
  ] as const) {
    await page
      .locator("main .sectiontabs")
      .getByRole("link", { name, exact: true })
      .click();
    await expect(page).toHaveURL("/administration/" + path + "/");
    await expect(page.locator("main")).not.toContainText("undefined");
  }
  await page
    .getByRole("button", { name: "Preview navigation by role" })
    .click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Account manager", exact: true })
    .click();
  await expect(page).toHaveURL("/");
  await expect(
    page
      .locator("#sidebar")
      .getByRole("link", { name: "Administration", exact: true }),
  ).not.toBeVisible();
});
test("attention categories and repair tasks persist across navigation", async ({
  page,
}) => {
  await page.goto("/attention/");
  await page.getByRole("button", { name: "Rankings", exact: true }).click();
  await expect(page.locator("main [data-attention-id]:visible")).toHaveCount(2);
  await page.locator('main [data-attention-id="3"] button').click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Create repair task" })
    .click();
  await page.goto("/clients/coastline-home-co/");
  await expect(page.locator("[data-upcoming-work]")).toContainText(
    "Review declining queries and repair links",
  );
});
test("connection inspection and source refresh preserve dialog focus", async ({
  page,
}) => {
  await page.goto(base + "/integrations/");
  await page
    .getByRole("button", { name: "View connection", exact: true })
    .nth(1)
    .click();
  await expect(
    page.getByRole("dialog").getByRole("heading", { level: 2 }),
  ).toHaveText("Google Search Console");
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Refresh sample sync" })
    .click();
  await expect(page.locator('main [data-source-sync="1"]')).toHaveText(
    "Just now",
  );
  await page.reload();
  await expect(page.locator('main [data-source-sync="1"]')).toHaveText(
    "Just now",
  );
});
test("automation overview filters select matching schedules and outcomes", async ({
  page,
}) => {
  await page.goto("/automations/");
  await page.getByLabel("Filter automations by client").selectOption("12");
  await expect(
    page.locator('[data-automation-group="upcoming"]:visible'),
  ).toHaveCount(3);
  await expect(
    page.locator('[data-automation-group="upcoming"]:visible').first(),
  ).toContainText("Cedar Home Services");
  await page.getByLabel("Filter automation type").selectOption("3");
  await expect(
    page.locator('[data-automation-group="upcoming"]:visible'),
  ).toHaveCount(1);
  await page.getByRole("button", { name: "Reset filters" }).click();
  await expect(
    page.locator('[data-automation-group="upcoming"]:visible'),
  ).toHaveCount(5);
});
test("local scan chart responds to the selected reporting period", async ({
  page,
}) => {
  await page.goto("/clients/northline-electric/local-search/");
  const path = await page.locator("[data-chart-current]").getAttribute("d");
  await page.getByLabel("Reporting date range").selectOption("7");
  await expect(page.locator('[data-chart-label="0"]')).toHaveText("Sep 23");
  expect(await page.locator("[data-chart-current]").getAttribute("d")).not.toBe(
    path,
  );
  await page.reload();
  await expect(page.locator('[data-chart-label="0"]')).toHaveText("Sep 23");
});
test("content and post edits survive normal page navigation", async ({
  page,
}) => {
  await page.goto(base + "/local-search/google-business-profile/");
  await page.getByRole("button", { name: "Edit scheduled post" }).click();
  await page
    .getByRole("dialog")
    .getByRole("textbox")
    .fill("Updated sample brunch post.");
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Save scheduled post" })
    .click();
  await page.reload();
  await page.getByRole("button", { name: "Edit scheduled post" }).click();
  await expect(page.getByRole("dialog").getByRole("textbox")).toHaveValue(
    "Updated sample brunch post.",
  );
});

test("GBP recovery restores metrics and removes expired authorization state", async ({
  page,
}) => {
  await page.goto(
    "/clients/pacific-restore/local-search/google-business-profile/",
  );
  await page.getByRole("button", { name: "Reconnect", exact: true }).click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Reconnect in prototype", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Google authorization expired" }),
  ).not.toBeVisible();
  await expect(page.locator("main .metrics")).toBeVisible();
  await page.goto("/clients/pacific-restore/");
  await expect(page.locator('[data-snapshot-index="2"] strong')).not.toHaveText(
    "Unavailable",
  );
  await page.goto("/clients/pacific-restore/integrations/");
  await expect(
    page.locator(
      'main [data-connection-source="0"][data-connection-field="status"]',
    ),
  ).toHaveText("Connected");
});
test("tracking recovery updates metrics and client insight across navigation", async ({
  page,
}) => {
  await page.goto("/clients/summit-electrical/leads/");
  await page.getByRole("button", { name: "Check tracking" }).click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Run tracking check" })
    .click();
  await expect(
    page.getByRole("heading", {
      name: "Conversion tracking requires attention",
    }),
  ).not.toBeVisible();
  await page.goto("/clients/summit-electrical/");
  await expect(page.locator('[data-snapshot-index="5"] strong')).toHaveText(
    "31",
  );
  await expect(page.locator('[data-client-insight="title"]')).toContainText(
    "Ranking declines",
  );
});
test("report review can progress from ready to sent", async ({ page }) => {
  await page.goto("/clients/palm-house-kitchen/reports/");
  await page.locator('main [data-command="openReport"]').first().click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Mark ready", exact: true })
    .click();
  await page.locator('main [data-command="openReport"]').first().click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Mark as sent", exact: true })
    .click();
  await page.locator('main [data-command="openReport"]').first().click();
  await expect(
    page
      .getByRole("dialog")
      .getByRole("button", { name: "Sent Sep 29", exact: true }),
  ).toBeDisabled();
});
test("sample edits remain scoped to their client", async ({ page }) => {
  await page.goto("/clients/northline-electric/settings/");
  await page.getByLabel("Business name").fill("Northline sample edit");
  await page.getByRole("button", { name: "Save settings" }).click();
  await page.goto("/clients/coco-maya/settings/");
  await expect(page.getByLabel("Business name")).toHaveValue("Coco Maya");
  await page.goto("/clients/northline-electric/settings/");
  await expect(page.getByLabel("Business name")).toHaveValue(
    "Northline sample edit",
  );
});
