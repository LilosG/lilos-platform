import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { png } from "./photo";
async function login(page: Page, target: string, who = "b") {
  await page.goto(`/login/?return=${encodeURIComponent(target)}`);
  await page.getByLabel("Email", { exact: true }).fill(`${who}@example.test`);
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
test("Local Search Overview carries every reference section except rankings", async ({
  page,
}) => {
  await login(page, "/clients/synthetic-beta/local-search/");
  const driving = page.locator("[data-overview-insights]");
  await expect(driving).toContainText("What is driving search performance");
  await expect(driving.locator(".listrow")).toHaveCount(3);
  await expect(driving).toContainText("Search clicks are up 14%");
  await expect(
    driving.getByRole("link", { name: "Landing pages" }),
  ).toHaveAttribute("href", /\/pages\//);
  const profile = page.locator("[data-overview-profile]");
  await expect(profile).toContainText("Calls");
  await expect(profile).toContainText("Business Profile · Last 28 days");
  await expect(profile).toContainText("Search Console · Last 28 days");
  const technical = page.locator("[data-overview-technical]");
  await expect(technical).toContainText("Indexed by Google");
  await expect(technical.locator("b.muted")).toHaveText(["Not tracked"]);
  await expect(technical).toContainText("24 of 26");
  const pages = page.locator("[data-overview-pages]");
  await expect(pages.locator(".badge")).toHaveText([
    "Indexable",
    "Indexable",
    "Indexable",
    "Indexable",
    "Not indexable",
  ]);
  const opportunities = page.locator("[data-overview-opportunities]");
  await expect(
    opportunities.getByRole("link", { name: "All findings" }),
  ).toHaveAttribute("href", "/clients/synthetic-beta/opportunities/");
  await expect(opportunities.locator(".badge").first()).toHaveText(
    /^(High|Medium|Low) priority$/,
  );
  // The reference's ranking sections have no data source yet and are not on the Overview.
  await expect(page.getByText("Ranking distribution")).toHaveCount(0);
  await expect(page.getByText("Competitor and search gaps")).toHaveCount(0);
  // No system text anywhere on the page.
  const text = await page.locator("main").innerText();
  expect(text).not.toMatch(
    /\b[A-Z]+(_[A-Z]+)+\b|[0-9a-f]{8}-[0-9a-f]{4}-|\d{4}-\d{2}-\d{2}T/,
  );
  await clean(page);
});
test("a photo is chosen, previewed, uploaded with progress and queued for approval", async ({
  page,
}) => {
  await login(page, `${gbp}?view=photos`);
  await page.getByRole("button", { name: "Add photo" }).first().click();
  const dialog = page.getByRole("dialog");
  const submit = dialog.getByRole("button", { name: "Upload for approval" });
  await expect(submit).toBeDisabled();
  // The browser refuses what Google would, before anything is sent.
  await dialog.getByLabel("Photo", { exact: true }).setInputFiles({
    name: "notes.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("not a picture".repeat(2000)),
  });
  await expect(dialog.locator("[data-form-status]")).toHaveText(
    "Use a JPG or PNG image.",
  );
  await dialog.getByLabel("Photo", { exact: true }).setInputFiles({
    name: "tiny.png",
    mimeType: "image/png",
    buffer: png(100, 100),
  });
  await expect(dialog.locator("[data-form-status]")).toContainText(
    "smaller than 250",
  );
  await dialog.getByLabel("Photo", { exact: true }).setInputFiles({
    name: "patio.png",
    mimeType: "image/png",
    buffer: png(320, 280),
  });
  await expect(dialog.locator("[data-photo-preview]")).toBeVisible();
  await expect(dialog.locator("[data-photo-facts]")).toContainText(
    "PNG · 320 × 280 px",
  );
  await expect(submit).toBeEnabled();
  await dialog
    .getByLabel("Who may use it")
    .selectOption("Owned by the business");
  const request = page.waitForRequest(
    (r) => r.method() === "POST" && r.url().endsWith("/media/"),
  );
  await submit.click();
  const sent = await request;
  expect(sent.headers()["content-type"]).toMatch(
    /^multipart\/form-data; boundary=/,
  );
  expect(Number((await sent.allHeaders())["content-length"])).toBeGreaterThan(
    10_000,
  );
  await expect(page.locator("[data-photo]")).toHaveCount(5);
  await expect(page.locator("[data-photo]").first()).toContainText(
    "Awaiting approval",
  );
  await clean(page);
});
test("a photo can be dropped onto the upload area", async ({ page }) => {
  await login(page, `${gbp}?view=photos`);
  await page.getByRole("button", { name: "Add photo" }).first().click();
  const dialog = page.getByRole("dialog");
  const bytes = [...png(300, 300)];
  await dialog.locator("[data-photo-drop]").evaluate((zone, data) => {
    const transfer = new DataTransfer();
    transfer.items.add(
      new File([new Uint8Array(data)], "drop.png", { type: "image/png" }),
    );
    zone.dispatchEvent(
      new DragEvent("drop", {
        dataTransfer: transfer,
        bubbles: true,
        cancelable: true,
      }),
    );
  }, bytes);
  await expect(dialog.locator("[data-photo-preview]")).toBeVisible();
  await expect(dialog.locator("[data-photo-facts]")).toContainText(
    "300 × 300 px",
  );
});
test("the rights statement is required before an upload goes", async ({
  page,
}) => {
  await login(page, `${gbp}?view=photos`);
  await page.getByRole("button", { name: "Add photo" }).first().click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Photo", { exact: true }).setInputFiles({
    name: "patio.png",
    mimeType: "image/png",
    buffer: png(300, 300),
  });
  await dialog.getByRole("button", { name: "Upload for approval" }).click();
  await expect(dialog.locator("[data-form-status]")).toHaveText(
    "Say who may use this photo.",
  );
});
test("special hours can be closed all day, which hides the times", async ({
  page,
}) => {
  await login(page, `${gbp}?view=special-hours`);
  await expect(
    page.locator("[data-hours]").filter({ hasText: "December 25, 2026" }),
  ).toContainText("Closed");
  await page.getByRole("button", { name: "Add special hours" }).first().click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByLabel("Opens")).toBeVisible();
  await dialog.getByLabel("Closed all day").check();
  await expect(dialog.getByLabel("Opens")).toBeHidden();
  await dialog.getByLabel("Date", { exact: true }).fill("2026-12-31");
  const request = page.waitForRequest(
    (r) => r.method() === "POST" && r.url().endsWith("/special-hours/"),
  );
  await dialog.getByRole("button", { name: "Save for approval" }).click();
  expect((await request).postDataJSON()).toEqual({
    service_date: "2026-12-31",
    closed: true,
    periods: [],
    source: "console",
  });
  const row = page
    .locator("[data-hours]")
    .filter({ hasText: "December 31, 2026" });
  await expect(row).toContainText("Closed all day");
  await expect(row.locator(".badge").first()).toHaveText("Closed");
  await clean(page);
});
test("open special hours still send their times", async ({ page }) => {
  await login(page, `${gbp}?view=special-hours`);
  await page.getByRole("button", { name: "Add special hours" }).first().click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Date", { exact: true }).fill("2026-12-30");
  const request = page.waitForRequest(
    (r) => r.method() === "POST" && r.url().endsWith("/special-hours/"),
  );
  await dialog.getByRole("button", { name: "Save for approval" }).click();
  expect((await request).postDataJSON()).toMatchObject({
    closed: false,
    periods: [{ opens: "09:00", closes: "17:00" }],
  });
});
test("the client Overview shows a priority band, not a score", async ({
  page,
}) => {
  await login(page, "/clients/synthetic-alpha/", "a");
  const chips = page.locator(".opportunitycard .badge");
  await expect(chips.first()).toHaveText(/^(High|Medium|Low) priority$/);
  await expect(page.locator("main")).not.toContainText(/Priority \d+/);
});
