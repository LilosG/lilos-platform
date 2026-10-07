import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
const base = "/clients/synthetic-alpha/website-content/";
const sim = "http://127.0.0.1:4455/test/website-scenario";
async function login(page: Page, target: string) {
  await page.goto(`/login/?return=${encodeURIComponent(target)}`);
  await page.getByLabel("Email", { exact: true }).fill("a@example.test");
  await page.getByLabel("Password", { exact: true }).fill("synthetic-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.waitForURL((url) => !url.pathname.startsWith("/login"));
  await page.locator('body[data-app-ready="true"]').waitFor();
}
const scenario = async (
  request: import("@playwright/test").APIRequestContext,
  mode: string,
) => request.post(sim, { data: { mode } });
const clean = async (page: Page) =>
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
// No ISO timestamp, UUID, enum value, availability code or scope string reaches a person.
const RAW =
  /\b[A-Z]+(_[A-Z]+)+\b|\b[a-z]+(_[a-z0-9]+)+\b|[0-9a-f]{8}-[0-9a-f]{4}-|\d{4}-\d{2}-\d{2}T|\bcanonical\b|permission_required|issues_detected|not_indexable|organization\b/i;
async function noRawText(page: Page) {
  const text = await page.locator("main").innerText();
  expect(text).not.toMatch(RAW);
  await expect(
    page.getByText(/\bundefined\b|\[object Object\]|\bNaN\b/),
  ).toHaveCount(0);
}
test.beforeEach(async ({ request }) => {
  await scenario(request, "rich");
});
test.afterEach(async ({ request }) => {
  await scenario(request, "default");
});

test("Overview: tiles, a typed insight, the page table and proposed changes", async ({
  page,
}) => {
  await login(page, base);
  await expect(
    page.getByRole("heading", { name: "Website & Content", level: 1 }),
  ).toBeVisible();
  const tiles = page.locator(".metric");
  await expect(tiles).toHaveCount(5);
  await expect(tiles.nth(0)).toContainText("8");
  await expect(tiles.nth(0)).toContainText("Pages checked");
  await expect(tiles.nth(3)).toContainText("2 days ago");
  // Google indexing is not collected: a designed muted tile, not a number.
  await expect(tiles.nth(4).locator("strong")).toHaveText("Not tracked");
  await expect(tiles.nth(4).locator("strong")).toHaveAttribute(
    "data-availability",
    "missing",
  );
  await expect(page.locator("[data-website-insight]")).toHaveAttribute(
    "data-website-insight",
    "ISSUES_FOUND",
  );
  await expect(page.locator("[data-performance-insight]")).toContainText(
    "4 pages have technical issues.",
  );
  const rows = page.locator("[data-page-row]");
  await expect(rows).toHaveCount(6);
  await expect(rows.first()).toContainText("/old-menu/");
  await expect(rows.first().locator(".badge")).toHaveText([
    "Indexable",
    "Issues found",
  ]);
  await expect(rows.first()).toContainText("2 days ago");
  const changes = page.locator("[data-site-changes] [data-site-change]");
  await expect(changes).toHaveCount(2);
  await expect(changes.first()).toContainText("Missing meta description");
  await expect(changes.first().locator(".badge")).toHaveText("High priority");
  // Sync runs and availability sit behind the header chip.
  await expect(page.getByText("Recent website checks")).toBeHidden();
  await expect(page.locator(".statuschip")).toContainText("Checked 2 days ago");
  await noRawText(page);
  await clean(page);
});

test("the header chip opens the Details dialog with checks and what is not collected", async ({
  page,
}) => {
  await login(page, base);
  await page.getByRole("button", { name: /Website data status/ }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toContainText("Recent website checks");
  await expect(dialog.locator(".badge")).toContainText([
    "Completed",
    "Partly checked",
  ]);
  await expect(dialog).toContainText("Stopped before every page was checked");
  await expect(dialog).toContainText("Google indexing status");
  const text = await dialog.innerText();
  expect(text.replaceAll(/https?:\/\/\S+/g, "")).not.toMatch(RAW);
  await clean(page);
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
});

test("the website selector is a designed control that keeps the tab", async ({
  page,
}) => {
  await login(page, base + "technical/");
  await expect(page.getByRole("button", { name: "Apply" })).toHaveCount(0);
  const select = page.getByLabel("Website", { exact: true });
  await expect(select).toHaveValue(/^11111111/);
  await expect(page.locator(".metric").first()).toContainText("8");
  await select.selectOption({ label: "Synthetic second site" });
  await page.waitForURL(/technical\/.*website_id=/);
  await expect(page).toHaveURL(/website-content\/technical\/\?website_id=0000/);
  await expect(page.locator(".metric").first()).toContainText("2");
  await expect(page.locator("[data-technical-findings]")).toContainText(
    "Missing page title",
  );
  // Tabs keep the chosen site.
  await page.getByRole("link", { name: "Pages", exact: true }).click();
  await expect(page).toHaveURL(/website-content\/pages\/\?website_id=0000/);
  await expect(page.locator("[data-page-row]")).toHaveCount(2);
  await noRawText(page);
});

test("Pages: search, filters with reasons, sort, and rows open the page", async ({
  page,
}) => {
  await login(page, base + "pages/");
  const rows = page.locator("[data-page-row]:not([hidden])");
  await expect(rows).toHaveCount(8);
  await expect(page.locator("[data-page-count]")).toHaveText("8 of 8 pages");
  await page.getByRole("searchbox", { name: "Search pages" }).fill("events");
  await expect(rows).toHaveCount(1);
  await expect(page.locator("[data-page-count]")).toHaveText("1 of 8 pages");
  await page.getByRole("searchbox", { name: "Search pages" }).fill("zzz");
  await expect(rows).toHaveCount(0);
  await expect(page.locator("[data-page-empty]")).toBeVisible();
  await page.getByRole("searchbox", { name: "Search pages" }).fill("");
  await page.getByRole("button", { name: "Has issues" }).click();
  await expect(rows).toHaveCount(4);
  await page.getByRole("button", { name: "Not indexable" }).click();
  await expect(rows).toHaveCount(1);
  await expect(rows.first()).toContainText("/gift-cards/");
  await page.getByRole("button", { name: "Not checked yet" }).click();
  await expect(rows).toHaveCount(1);
  await expect(rows.first()).toContainText("/jobs/");
  await expect(rows.first()).toContainText("Not checked");
  // A filter without a source stays, disabled, with its reason.
  const drafts = page.getByRole("button", { name: "Drafts" });
  await expect(drafts).toBeDisabled();
  await expect(drafts).toHaveAttribute(
    "title",
    "Draft pages are not tracked yet",
  );
  await expect(
    page.getByRole("option", { name: /Organic clicks \(not tracked\)/ }),
  ).toBeDisabled();
  await page.getByRole("button", { name: "All pages" }).click();
  await page.getByLabel("Sort pages").selectOption("name");
  await expect(rows.first()).toContainText("/gift-cards/");
  await expect(rows.last()).toContainText("Synthetic reservations");
  await noRawText(page);
  await clean(page);
  await page
    .locator("[data-page-row]", { hasText: "/menu/" })
    .getByRole("link", { name: "Synthetic menu", exact: true })
    .click();
  await expect(page).toHaveURL(/pages\/11111111-[^/]+\/0{7}2-/);
  await expect(
    page.getByRole("heading", { name: "Synthetic menu" }),
  ).toBeVisible();
});

test("the page table fits its screen: no clipped columns at 1440, a clean scroll at 390", async ({
  page,
}, info) => {
  await login(page, base + "pages/");
  const wrap = page.locator(".tablewrap.pagetable");
  await expect(wrap).toBeVisible();
  const fit = await wrap.evaluate((el) => ({
    scroll: el.scrollWidth,
    client: el.clientWidth,
    page: document.documentElement.scrollWidth,
    view: window.innerWidth,
    headers: [...el.querySelectorAll("th")].map((th) => {
      const box = th.getBoundingClientRect();
      const frame = el.getBoundingClientRect();
      return box.left >= frame.left - 1 && box.right <= frame.right + 1;
    }),
  }));
  // The page itself never scrolls sideways.
  expect(fit.page).toBeLessThanOrEqual(fit.view);
  if (info.project.name === "desktop") {
    expect(fit.scroll).toBeLessThanOrEqual(fit.client);
    expect(fit.headers.every(Boolean)).toBe(true);
    for (const heading of [
      "Page",
      "Status",
      "Indexability",
      "Quality",
      "Findings",
      "Last checked",
    ])
      await expect(
        wrap.getByRole("columnheader", { name: heading }),
      ).toBeInViewport();
  } else {
    // On a phone the table scrolls inside its own frame, reachable by keyboard.
    expect(fit.scroll).toBeGreaterThan(fit.client);
    await expect(wrap).toHaveAttribute("tabindex", "0");
    expect(await wrap.evaluate((el) => getComputedStyle(el).overflowX)).toBe(
      "auto",
    );
  }
});

test("Technical: findings grouped by severity, each with a next action", async ({
  page,
}) => {
  await login(page, base + "technical/");
  const groups = page.locator("[data-technical-findings] h3.subhead");
  await expect(groups).toHaveText([
    /High priority/,
    /Medium priority/,
    /Low priority/,
  ]);
  const finding = page.locator("[data-finding]", {
    hasText: "Missing page title",
  });
  await expect(finding.locator(".badge")).toHaveText("High priority");
  await expect(finding).toContainText("Affects 1 page");
  await expect(
    finding.getByRole("link", { name: "Review proposed change" }),
  ).toHaveAttribute("href", /\/clients\/synthetic-alpha\/opportunities\//);
  const gone = page.locator("[data-finding]", {
    hasText: "Page does not load correctly",
  });
  await expect(gone.getByRole("link", { name: "Open page" })).toHaveAttribute(
    "href",
    /\/pages\//,
  );
  // An unknown crawler code is still worded, never printed raw.
  await expect(
    page.locator("[data-finding]", { hasText: "Some future code" }),
  ).toHaveCount(1);
  await expect(page.locator(".metric").nth(2)).toContainText("2");
  await expect(
    page.locator("[data-site-changes] [data-site-change]"),
  ).toHaveCount(2);
  await noRawText(page);
  await clean(page);
});

test("Conversions is a designed empty state with a next action and never shows 0", async ({
  page,
}) => {
  await login(page, base + "conversions/");
  const tiles = page.locator(".metric strong");
  await expect(tiles).toHaveText(["Not tracked", "Not tracked", "Not tracked"]);
  const empty = page.locator("[data-website-conversions]");
  await expect(
    empty.getByRole("heading", {
      name: "Conversion paths are not tracked yet",
    }),
  ).toBeVisible();
  await expect(
    empty.getByRole("link", { name: "Connect Analytics" }),
  ).toHaveAttribute("href", "/clients/synthetic-alpha/integrations/");
  await expect(
    empty.getByRole("link", { name: "Inspect page evidence" }),
  ).toHaveAttribute("href", /website-content\/pages\//);
  expect(await page.locator("main").innerText()).not.toMatch(/(^|\s)0(\s|$)/);
  await noRawText(page);
  await clean(page);
});

test("page detail: evidence, repository link and proposed changes", async ({
  page,
}) => {
  await login(page, base + "pages/");
  await page
    .locator("[data-page-row]", { hasText: "/menu/" })
    .getByRole("link", { name: "Open Synthetic menu" })
    .click();
  const dialog = page.getByRole("dialog");
  await expect(
    dialog.getByRole("heading", { name: "Synthetic menu" }),
  ).toBeVisible();
  await expect(dialog).toContainText("Synthetic hospitality site · /menu/");
  await expect(dialog.locator(".detailmetrics")).toContainText("640");
  await expect(dialog.locator("[data-evidence]").first()).toContainText(
    "150 clicks · 4,300 impressions",
  );
  await expect(dialog.locator("[data-page-mapping] .badge")).toHaveText(
    "Repository linked",
  );
  await dialog.getByText("Repository details").click();
  await expect(dialog).toContainText("synthetic/restaurant-site");
  await expect(dialog.locator("[data-site-change]")).toHaveCount(1);
  await expect(
    dialog.getByRole("link", { name: /Missing meta description/ }),
  ).toHaveAttribute("href", /opportunities\//);
  const text = await dialog.innerText();
  expect(text).not.toMatch(
    /\bundefined\b|SITE_MAPPING|[0-9a-f]{8}-[0-9a-f]{4}-|\d{4}-\d{2}-\d{2}T/,
  );
  await clean(page);
  await dialog.getByRole("link", { name: "All pages" }).click();
  await expect(page).toHaveURL(/website-content\/pages\/\?website_id=/);
});

test("page detail without a repository link or evidence is designed, not blank", async ({
  page,
  request,
}) => {
  await scenario(request, "clean");
  await login(page, base + "pages/");
  await page
    .locator("[data-page-row]", { hasText: "/menu/" })
    .getByRole("link", { name: "Open Synthetic menu" })
    .click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.locator("[data-page-mapping] .badge")).toHaveText(
    "Repository not linked",
  );
  await expect(dialog).toContainText(
    "not linked to a file in the client's website repository",
  );
  await expect(
    dialog.getByRole("link", { name: "Open Integrations" }),
  ).toBeVisible();
  await expect(dialog.locator("[data-evidence] .badge").first()).toHaveText(
    "Not tracked",
  );
  await expect(
    dialog.getByRole("heading", { name: "No proposed changes for this page" }),
  ).toBeVisible();
  expect(await dialog.innerText()).not.toMatch(/SITE_MAPPING_REQUIRED/);
  await clean(page);
});

for (const [mode, tabs] of [
  ["empty", ["", "pages", "technical"]],
  ["no_website", ["", "pages", "technical"]],
  ["no_access", ["", "pages", "technical"]],
  ["unavailable", ["", "pages", "technical"]],
  ["clean", ["", "technical"]],
  ["failed", [""]],
] as const)
  test(`not-connected and empty states (${mode}) are designed with a next action`, async ({
    page,
    request,
  }) => {
    await scenario(request, mode);
    await login(page, base);
    for (const tab of tabs) {
      await page.goto(base + (tab ? tab + "/" : ""));
      await expect(page.locator("div.empty, .banner").first()).toBeVisible();
      // A figure that is missing is never shown as 0; a measured zero (pages checked, none
      // with issues) is a real count and only appears where pages were checked.
      const values = await page.locator(".metric strong").allInnerTexts();
      if (mode !== "clean" && mode !== "failed")
        expect(values.map((value) => value.trim())).not.toContain("0");
      await noRawText(page);
    }
    await clean(page);
  });

test("the empty states name what to do next", async ({ page, request }) => {
  await scenario(request, "empty");
  await login(page, base + "pages/");
  await expect(
    page.getByRole("heading", { name: "No pages have been checked yet" }),
  ).toBeVisible();
  await expect(
    page.locator(".empty").getByRole("button", { name: "Run a website check" }),
  ).toBeVisible();
  await page.goto(base);
  await expect(page.locator("[data-website-insight]")).toHaveAttribute(
    "data-website-insight",
    "NEVER_CHECKED",
  );
  await expect(page.locator(".metric strong").first()).toHaveText(
    "Not checked",
  );
  await expect(page.locator(".statuschip")).toContainText("Not checked yet");
  await scenario(request, "no_website");
  await page.goto(base);
  await expect(
    page.getByRole("heading", { name: "No website to show" }),
  ).toBeVisible();
  await expect(
    page.locator(".empty").getByRole("link", { name: "Open Integrations" }),
  ).toBeVisible();
  await expect(page.getByLabel("Website", { exact: true })).toHaveCount(0);
  await scenario(request, "no_access");
  await page.goto(base + "technical/");
  await expect(
    page.getByRole("heading", { name: "You do not have access to page data" }),
  ).toBeVisible();
  await scenario(request, "clean");
  await page.goto(base + "technical/");
  await expect(
    page.getByRole("heading", { name: "No technical issues found" }),
  ).toBeVisible();
  await expect(page.locator(".metric strong").nth(2)).toHaveText("0");
  await scenario(request, "failed");
  await page.goto(base);
  await expect(page.locator("[data-website-insight]")).toHaveAttribute(
    "data-website-insight",
    "LAST_CHECK_FAILED",
  );
  await expect(page.locator(".statuschip")).toContainText("Last check failed");
});

for (const path of ["", "pages/", "technical/", "conversions/", "content/"])
  test(`error state on ${path || "overview"} is a designed ErrorState with a retry`, async ({
    page,
    request,
  }) => {
    await login(page, base);
    await scenario(request, "error");
    await page.goto(base + path);
    const banner = page.getByRole("alert");
    await expect(
      banner.getByRole("heading", { name: "Website data could not be loaded" }),
    ).toBeVisible();
    await expect(
      banner.getByRole("link", { name: "Try again" }),
    ).toHaveAttribute("href", new RegExp(`${path}$`));
    await expect(page.locator("main")).not.toContainText(
      /INTERNAL|500|This source is temporarily/,
    );
    await clean(page);
  });

test("page detail error is designed", async ({ page, request }) => {
  await login(page, base);
  await scenario(request, "error");
  await page.goto(
    `${base}pages/11111111-1111-4111-8111-111111111111/00000002-0000-4000-8000-000000000000/`,
  );
  await expect(
    page.getByRole("heading", { name: "Website data could not be loaded" }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: "Try again" })).toBeVisible();
});

test("the website check can be started; its outcome is stated in plain words", async ({
  page,
}) => {
  await login(page, base);
  const request = page.waitForRequest(
    (r) => r.method() === "POST" && r.url().endsWith("/check/"),
  );
  await page.getByRole("button", { name: "Run website check" }).click();
  const sent = await request;
  expect(sent.postDataJSON().idempotency_key).toMatch(/^[0-9a-f-]{36}$/);
  await expect(page.locator("[data-website-status]")).toHaveText(
    "Website check started. Refresh in a few minutes to see the results.",
  );
  await expect(
    page.getByRole("button", { name: "Run website check" }),
  ).toBeDisabled();
});

test("a role that cannot start checks sees the control disabled with its reason", async ({
  page,
  request,
}) => {
  await scenario(request, "no_access");
  await login(page, base);
  const button = page.getByRole("button", { name: "Run website check" });
  await expect(button).toBeDisabled();
  await expect(button).toHaveAttribute(
    "title",
    "Your role cannot start website checks",
  );
});

test("the Content tab lists content and offers the composer", async ({
  page,
}) => {
  await login(page, base + "content/");
  await expect(
    page.getByRole("heading", { name: /Articles and guides/ }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "New content" })).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Content", exact: true }),
  ).toHaveAttribute("aria-current", "page");
});
