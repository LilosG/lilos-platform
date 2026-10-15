import { mkdir, writeFile } from "node:fs/promises";
import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
const sim = "http://127.0.0.1:4455/test";
const visual = new URL(
  "../../visual/step-10b-report-redesign/",
  import.meta.url,
);
async function scenario(mode: string) {
  const response = await fetch(`${sim}/reports-scenario`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode }),
  });
  expect(response.ok).toBe(true);
}
async function login(page: Page, who: string, target: string) {
  // The client document has no app shell, so it never marks the app ready.
  const shell = !target.endsWith("/document/");
  await page.goto(`/login/?return=${encodeURIComponent(target)}`);
  await page.getByLabel("Email", { exact: true }).fill(`${who}@example.test`);
  await page.getByLabel("Password", { exact: true }).fill("synthetic-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.waitForURL((url) => !url.pathname.startsWith("/login"));
  if (shell) await page.locator('body[data-app-ready="true"]').waitFor();
}
const clean = async (page: Page) => {
  const found = (await new AxeBuilder({ page }).analyze()).violations.map(
    (item) =>
      `${item.id}: ${item.nodes.map((node) => node.target.join(" ")).join(" | ")}`,
  );
  expect(found).toEqual([]);
};
/** No ISO timestamp, enum value, identifier or API text in what a person reads. */
const noSystemText = async (page: Page, selector = "main") => {
  const text = await page.locator(selector).innerText();
  expect(text).not.toMatch(
    /\b[A-Z]+(_[A-Z]+)+\b|\b[a-z]+(_[a-z]+)+\b|[0-9a-f]{8}-[0-9a-f]{4}-|\d{4}-\d{2}-\d{2}/,
  );
  expect(text).not.toMatch(/NaN|undefined/);
};
test.beforeEach(async () => scenario("default"));
test.describe("the generate dialog", () => {
  test("offers the presets, refuses a bad period with a sentence, and generates a range", async ({
    page,
  }) => {
    await login(page, "admin", "/clients/synthetic-alpha/reports/");
    await page.getByRole("link", { name: "New report" }).first().click();
    const dialog = page.locator("dialog[open]");
    await expect(
      dialog.getByRole("heading", { name: "New report" }),
    ).toBeVisible();
    await expect(dialog).toContainText("Reports cover whole calendar months");
    await expect(dialog.getByLabel("Period", { exact: true })).toHaveValue(
      "last-month",
    );
    await expect(
      dialog.getByLabel("Period", { exact: true }).locator("option"),
    ).toHaveText([
      "Last month",
      "Last 3 months",
      "Last 6 months",
      "Year to date",
      "Choose months",
    ]);
    // Only months that have ended can be chosen.
    await expect(
      dialog
        .getByLabel("Last month", { exact: true })
        .locator("option")
        .first(),
    ).toHaveText("September 2026");
    await expect(
      dialog.getByLabel("Last month", { exact: true }),
    ).not.toContainText("October 2026");
    await expect(
      dialog.getByLabel("Compare with", { exact: true }),
    ).toHaveValue("previous");
    await noSystemText(page, "dialog[open]");

    // The last month cannot come before the first.
    await dialog
      .getByLabel("First month", { exact: true })
      .selectOption("2026-09-01");
    await dialog
      .getByLabel("Last month", { exact: true })
      .selectOption("2026-07-01");
    await expect(dialog.getByRole("alert").first()).toHaveText(
      "The last month cannot be before the first month.",
    );
    await expect(
      dialog.getByRole("button", { name: "Generate report" }),
    ).toBeDisabled();
    // Thirteen months are too many.
    await dialog
      .getByLabel("First month", { exact: true })
      .selectOption("2025-09-01");
    await dialog
      .getByLabel("Last month", { exact: true })
      .selectOption("2026-09-01");
    await expect(dialog.getByRole("alert").first()).toHaveText(
      "A report covers 1 to 12 whole months.",
    );
    await expect(dialog.getByLabel("Period", { exact: true })).toHaveValue(
      "custom",
    );
    // A baseline must end before the report starts.
    await dialog.getByLabel("Period", { exact: true }).selectOption("last-6");
    await expect(
      dialog.getByRole("button", { name: "Generate report" }),
    ).toBeEnabled();
    await dialog
      .getByLabel("Compare with", { exact: true })
      .selectOption("baseline");
    await dialog
      .getByLabel("Baseline first month", { exact: true })
      .selectOption("2026-05-01");
    await dialog
      .getByLabel("Baseline last month", { exact: true })
      .selectOption("2026-06-01");
    await expect(
      dialog.getByText(
        "The baseline must end before the report period starts.",
      ),
    ).toBeVisible();
    await expect(
      dialog.getByRole("button", { name: "Generate report" }),
    ).toBeDisabled();
    await clean(page);
    await page
      .screenshot({
        path: new URL(
          `dialog-validation-${test.info().project.name}.png`,
          visual,
        ).pathname,
      })
      .catch(() => undefined);

    await dialog
      .getByLabel("Baseline first month", { exact: true })
      .selectOption("2026-01-01");
    await dialog
      .getByLabel("Baseline last month", { exact: true })
      .selectOption("2026-02-01");
    await dialog.getByRole("button", { name: "Generate report" }).click();
    await page.waitForURL(
      /\/reports\/2026-04_2026-09\/\?vs=2026-01_2026-02&revision=1$/,
    );
    await expect(page.locator("h1")).toHaveText(
      "April – September 2026 performance report",
    );
    await expect(page.locator("main")).toContainText(
      "April 1 – September 30, 2026",
    );
    await noSystemText(page);

    await page.goto("/clients/synthetic-alpha/reports/");
    await expect(page.locator("tbody")).toContainText("April – September 2026");
    await expect(page.locator("tbody")).toContainText(
      "vs January – February 2026",
    );
  });
  test("year to date compared with the same period last year", async ({
    page,
  }) => {
    await login(page, "admin", "/clients/synthetic-alpha/reports/new/");
    const dialog = page.locator("dialog[open]");
    await dialog
      .getByLabel("Period", { exact: true })
      .selectOption("year-to-date");
    await expect(dialog.getByLabel("First month", { exact: true })).toHaveValue(
      "2026-01-01",
    );
    await dialog
      .getByLabel("Compare with", { exact: true })
      .selectOption("year-ago");
    await expect(dialog).toContainText("The same months one year earlier.");
    await dialog.getByRole("button", { name: "Generate report" }).click();
    await page.waitForURL(
      /\/reports\/2026-01_2026-09\/\?vs=year-ago&revision=1$/,
    );
    await expect(page.locator("h1")).toHaveText(
      "January – September 2026 performance report",
    );
  });
  test("a baseline right before the period is allowed", async ({ page }) => {
    await login(page, "admin", "/clients/synthetic-alpha/reports/new/");
    const dialog = page.locator("dialog[open]");
    await dialog
      .getByLabel("Compare with", { exact: true })
      .selectOption("baseline");
    await dialog
      .getByLabel("Baseline first month", { exact: true })
      .selectOption("2026-08-01");
    await dialog
      .getByLabel("Baseline last month", { exact: true })
      .selectOption("2026-08-01");
    await expect(
      dialog.getByRole("button", { name: "Generate report" }),
    ).toBeEnabled();
    await dialog.getByRole("button", { name: "Generate report" }).click();
    await page.waitForURL(/\/reports\/2026-09\/\?vs=2026-08&revision=1$/);
    await expect(page.locator("main")).toContainText("compared with");
  });
});
test.describe("the report page", () => {
  test("shows the period and comparison, the headline figures and the scorecard", async ({
    page,
  }) => {
    await scenario("range");
    await login(
      page,
      "admin",
      "/clients/synthetic-alpha/reports/2026-05_2026-09/",
    );
    await expect(page.locator("h1")).toHaveText(
      "May – September 2026 performance report",
    );
    await expect(page.locator("main")).toContainText(
      "compared with the months before (December 2025 – April 2026)",
    );
    await expect(page.getByText("Profile views").first()).toBeVisible();
    await expect(
      page.getByRole("columnheader", { name: "Compared with" }),
    ).toBeVisible();
    await expect(
      page.getByRole("link", { name: "Download PDF" }),
    ).toBeVisible();
    await noSystemText(page);
    await clean(page);
    await page.getByRole("button", { name: /^Details/ }).click();
    await expect(page.locator("#report-notes")).toContainText("Report details");
    await mkdir(visual, { recursive: true });
  });
  test("Download PDF opens the document and prints it", async ({
    page,
    context,
  }) => {
    await scenario("range");
    await context.addInitScript(() => {
      (window as unknown as { printed: number }).printed = 0;
      window.print = () => {
        (window as unknown as { printed: number }).printed++;
      };
    });
    await login(
      page,
      "admin",
      "/clients/synthetic-alpha/reports/2026-05_2026-09/",
    );
    const popup = page.waitForEvent("popup");
    await page.getByRole("link", { name: "Download PDF" }).click();
    const opened = await popup;
    await opened.waitForLoadState("load");
    expect(opened.url()).toContain("/reports/2026-05_2026-09/document/");
    expect(opened.url()).toContain("revision=1");
    await expect
      .poll(() =>
        opened.evaluate(
          () => (window as unknown as { printed: number }).printed,
        ),
      )
      .toBe(1);
  });
  test("approving names the period and the dates", async ({ page }) => {
    await login(page, "admin", "/clients/synthetic-alpha/reports/new/");
    await page.getByLabel("Period", { exact: true }).selectOption("last-3");
    await page.getByRole("button", { name: "Generate report" }).click();
    await page.waitForURL(/\/reports\/2026-07_2026-09\/\?revision=1$/);
    await page.getByRole("button", { name: "Draft with Hermes" }).click();
    await page.getByRole("button", { name: "Approve", exact: true }).click();
    await expect(page.locator("#report-confirm")).toContainText(
      "Synthetic Alpha · July – September 2026 (July 1 – September 30, 2026).",
    );
  });
});
test.describe("the client document", () => {
  const url = "/clients/synthetic-alpha/reports/2026-05_2026-09/document/";
  test("is a chrome-free report with every section in order", async ({
    page,
  }) => {
    await scenario("range");
    await login(page, "admin", url);
    // No app header, navigation or buttons.
    await expect(
      page.locator("nav, aside, header.appheader, .sidebar"),
    ).toHaveCount(0);
    await expect(page.getByRole("button")).toHaveCount(0);
    await expect(page.locator("h1")).toHaveText(
      "Coco Maya".replace("Coco Maya", "Synthetic Alpha"),
    );
    await expect(page.locator(".cover")).toContainText("May – September 2026");
    await expect(page.locator(".cover")).toContainText(
      "Compared with: December 2025 – April 2026",
    );
    await expect(page.locator(".cover")).toContainText("Lilos Growth");
    const headings = await page.locator("h2").allInnerTexts();
    expect(headings.map((text) => text.replace(/^\d+\s*/, "").trim())).toEqual([
      "This period at a glance",
      "Scorecard",
      "Google Business Profile",
      "Website search",
      "Reviews",
      "Work completed",
      "Looking ahead",
      "Notes and definitions",
    ]);
    await expect(page.locator("[data-headline]")).toHaveCount(4);
    await expect(page.locator(".prose").first()).toContainText(
      "Across May to September",
    );
    await expect(
      page.getByRole("columnheader", { name: "Same period last year" }),
    ).toBeVisible();
    await expect(page.getByText("and 87 more")).toBeVisible();
    await expect(page.getByText("Not included in this report")).toBeVisible();
    await expect(
      page.getByText("Local search ranking: not tracked yet"),
    ).toBeVisible();
    // Every chart has a text alternative.
    const charts = page.locator("figure.docchart svg");
    expect(await charts.count()).toBeGreaterThanOrEqual(6);
    for (const svg of await charts.all()) {
      await expect(svg).toHaveAttribute("role", "img");
      expect(await svg.locator("title").textContent()).toBeTruthy();
      expect((await svg.locator("desc").textContent())?.length).toBeGreaterThan(
        20,
      );
    }
    await noSystemText(page, "article.doc");
    await clean(page);
    // Nothing runs off the side of a phone.
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth + 1,
      ),
    ).toBe(true);
  });
  test("leaves partial and missing data out of the numbers and says so", async ({
    page,
  }) => {
    await scenario("gaps");
    await login(page, "admin", url);
    await expect(page.locator("[data-section=scorecard]")).toContainText(
      "Not comparable",
    );
    await expect(page.locator("[data-section=scorecard]")).toContainText("*");
    await expect(page.locator("[data-section=scorecard]")).toContainText(
      "Search figures cover only the months Google has delivered so far",
    );
    await expect(page.locator("[data-section=scorecard]")).toContainText(
      "Google reported no bookings this period (45 in the comparison period). This can reflect a change in how Google reports it, not lower demand.",
    );
    // Google Analytics is not connected: no section, no row, and a line under Notes.
    await expect(page.locator("[data-section=scorecard]")).not.toContainText(
      "Visits from search",
    );
    await expect(page.locator("[data-section=notes]")).toContainText(
      "Website visits from Google Analytics: not connected",
    );
    await expect(page.locator("article.doc")).not.toContainText("-100%");
    await noSystemText(page, "article.doc");
    await clean(page);
  });
  test("prints to a PDF of 12 pages or fewer on Letter paper", async ({
    page,
  }) => {
    test.skip(test.info().project.name !== "desktop", "one PDF is enough");
    await scenario("range");
    await login(page, "admin", url);
    await page.emulateMedia({ media: "print" });
    await page.evaluate(() => document.fonts.ready);
    const pdf = await page.pdf({
      preferCSSPageSize: true,
      printBackground: true,
    });
    await mkdir(visual, { recursive: true });
    await writeFile(new URL("report-document.pdf", visual), pdf);
    const text = pdf.toString("latin1");
    const counts = [
      ...text.matchAll(/\/Type\s*\/Pages[^>]*?\/Count\s+(\d+)/g),
    ].map((m) => Number(m[1]));
    const pages = counts.length
      ? Math.max(...counts)
      : (text.match(/\/Type\s*\/Page[^s]/g) ?? []).length;
    expect(pages).toBeGreaterThanOrEqual(5);
    expect(pages).toBeLessThanOrEqual(12);
    // Letter: 8.5 x 11 inches.
    expect(text).toMatch(
      /\/MediaBox\s*\[\s*0\s+0\s+612(\.0+)?\s+792(\.0+)?\s*\]/,
    );
  });
});
