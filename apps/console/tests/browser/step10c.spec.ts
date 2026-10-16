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
async function login(page: Page, target: string) {
  await page.goto(`/login/?return=${encodeURIComponent(target)}`);
  await page.getByLabel("Email", { exact: true }).fill("admin@example.test");
  await page.getByLabel("Password", { exact: true }).fill("synthetic-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.waitForURL((url) => !url.pathname.startsWith("/login"));
}
const full = "/clients/synthetic-alpha/reports/2026-09/document/";
const sparse =
  "/clients/synthetic-beta/reports/2026-05_2026-09/document/?vs=2025-12_2026-04";
test.beforeEach(async () => scenario("default"));
test.describe("the client document reads like a report", () => {
  test("opens with a timeline, result cards, topics and gains", async ({
    page,
  }) => {
    await scenario("document");
    await login(page, full);
    await expect(page.locator("[data-timeline] li")).toHaveCount(3);
    await expect(page.locator(".cover")).toContainText(
      "Synthetic Alpha Downtown",
    );
    await expect(page.locator("[data-draft-banner]")).toHaveCount(0);
    const cards = page.locator("[data-result]");
    await expect(cards).toHaveCount(4);
    await expect(page.locator("[data-result].headline")).toHaveCount(1);
    await expect(cards.first()).toContainText("+80%");
    await expect(cards.first()).toContainText(
      "More first-page Google rankings",
    );
    await expect(cards.first().locator(".foot")).toContainText(
      "Search Console",
    );
    // Topics and gains, with positions as people read them.
    await expect(page.locator("[data-topics]")).toContainText("Happy hour");
    await expect(page.locator("[data-gains]")).toContainText("#7.5 → #3.2");
    await expect(page.locator("[data-gains]")).toContainText("New → #9.5");
    // The misspelled brand search is in no topic and not in the gains.
    await expect(page.locator("[data-gains]")).not.toContainText("cocomaia");
    // Every chart and table says what to take from it.
    for (const figure of await page.locator("figure.docchart").all())
      await expect(figure.locator(".dcaption")).not.toBeEmpty();
    await expect(
      page.locator("[data-section=scorecard] tbody tr:not(.group) th").first(),
    ).toContainText("Google Business Profile");
    const text = await page.locator("article.doc").innerText();
    expect(text).not.toMatch(
      /\b[A-Z]+(_[A-Z]+)+\b|\b[a-z]+(_[a-z]+)+\b|\d{4}-\d{2}-\d{2}|NaN|undefined/,
    );
    const found = (await new AxeBuilder({ page }).analyze()).violations;
    expect(found.map((item) => item.id)).toEqual([]);
  });
  test("a thin, draft report omits what it cannot state and is marked a draft", async ({
    page,
  }) => {
    await scenario("sparse");
    await login(page, sparse);
    await expect(page.locator("[data-draft-banner]")).toHaveText(
      "Draft - not for sending",
    );
    // No milestones in the business facts: no strip. One internal location: no names.
    await expect(page.locator("[data-timeline]")).toHaveCount(0);
    await expect(page.locator(".cover")).not.toContainText("Main");
    // No search data before May: nothing is set against it, and no gains are invented.
    await expect(page.locator("[data-gains]")).toHaveCount(0);
    await expect(page.locator("[data-search-tiles]")).not.toContainText("was ");
    await expect(page.locator("[data-section=search]")).toContainText(
      "Google Search Console, non-branded searches only",
    );
    await expect(page.locator("[data-section=scorecard]")).toContainText(
      "Not synced yet",
    );
    // Four addresses of the home page are one row.
    const pages = page.getByRole("row", { name: /^Home page/ });
    await expect(pages).toHaveCount(1);
    // Google stopped reporting bookings: the reason sits beside the figure.
    await expect(page.locator("[data-section=scorecard]")).toContainText(
      "Google reported no bookings this period (28 in the comparison period)",
    );
    // Search clicks have no comparison months, so no card is written about them.
    await expect(page.locator("[data-result]")).toHaveCount(2);
  });
  test("prints on warm paper with readable type and no page left mostly empty", async ({
    page,
  }) => {
    test.skip(test.info().project.name !== "desktop", "one print is enough");
    await scenario("document");
    await login(page, full);
    await page.emulateMedia({ media: "print" });
    await page.evaluate(() => document.fonts.ready);
    const sizes = await page.evaluate(() => {
      const pt = (px: number) => px * 0.75;
      const small: string[] = [];
      for (const el of document.querySelectorAll("article.doc *")) {
        const own = [...el.childNodes].some(
          (n) => n.nodeType === 3 && (n.textContent ?? "").trim() !== "",
        );
        if (!own) continue;
        const style = getComputedStyle(el);
        let size = parseFloat(style.fontSize);
        if (el instanceof SVGGraphicsElement) {
          const ctm = el.getScreenCTM();
          if (ctm) size *= ctm.a;
        }
        const inTable = !!el.closest("table");
        const floor =
          inTable || el.closest(".foot, .kicker, .tilelabel") ? 8.5 : 9;
        if (pt(size) < floor - 0.1)
          small.push(`${el.tagName}.${el.className}: ${pt(size).toFixed(1)}pt`);
      }
      return small;
    });
    expect(sizes).toEqual([]);
    const paper = await page.evaluate(
      () => getComputedStyle(document.body).backgroundColor,
    );
    expect(paper).toBe("rgb(246, 245, 242)");
    const printAdjust = await page.evaluate(() =>
      getComputedStyle(document.body).getPropertyValue("print-color-adjust"),
    );
    expect(printAdjust).toBe("exact");
  });
});
test.describe("result cards are editable before approval", () => {
  test("edit a card's words; its figures stay", async ({ page }) => {
    await scenario("sparse");
    await login(
      page,
      "/clients/synthetic-beta/reports/2026-05_2026-09/?vs=2025-12_2026-04&revision=1",
    );
    await expect(
      page.getByRole("link", { name: "Download draft PDF" }),
    ).toBeVisible();
    const title = page.getByLabel("Card 1 title");
    await title.fill("More people found the profile this spring");
    await page.getByRole("button", { name: "Save narrative" }).first().click();
    await expect(page.getByText("Narrative saved.")).toBeVisible();
    await page.reload();
    await expect(page.getByLabel("Card 1 title")).toHaveValue(
      "More people found the profile this spring",
    );
  });
});
