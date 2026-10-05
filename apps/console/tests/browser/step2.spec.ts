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
test("Dashboard shows real states, never fixtures or invented zeros", async ({
  page,
}) => {
  await login(page);
  await expect(
    page.getByRole("heading", { name: "Portfolio overview" }),
  ).toBeVisible();
  await expect(page.locator("body")).not.toContainText("SAMPLE DATA");
  await expect(page.locator("body")).not.toContainText("Prototype");
  // Local visibility is not tracked until rank scans exist.
  await expect(
    page.locator(".metric", { hasText: "Local visibility" }),
  ).toContainText("Not tracked");
  await expect(
    page.getByRole("button", { name: "Google post publishing failed" }),
  ).toBeVisible();
  await expect(page.getByText("Missing meta description: /menu")).toBeVisible();
  const row = page.locator("[data-client-row]").first();
  await expect(row).toContainText("Synthetic Alpha");
  await expect(row.locator("td").nth(1)).toContainText("Not tracked");
  await expect(row.locator("td").nth(2)).toContainText("Not tracked");
  await expect(row.locator("td").nth(3)).toContainText("1,240");
  await expect(page.locator("#rowcount")).toHaveText("1 of 1 clients");
  await clean(page);
});
test("Attention dialog, period control and filters", async ({ page }) => {
  await login(page);
  await page
    .getByRole("button", {
      name: "Google Business Profile needs to be reconnected",
    })
    .click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toContainText("Recommended next action");
  await dialog.getByRole("button", { name: "Close details" }).click();
  await page
    .getByRole("button", { name: "Google post publishing failed" })
    .click();
  await expect(page.getByRole("dialog")).toContainText("What failed");
  await expect(page.getByRole("dialog")).toContainText("PROVIDER_REJECTED");
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Close details" })
    .click();
  await page.getByLabel("Reporting date range").selectOption("90");
  await expect(page).toHaveURL(/days=90/);
  await page.getByRole("button", { name: "Improving" }).isDisabled();
  await expect(page.getByRole("button", { name: "Improving" })).toBeDisabled();
  await page.getByLabel("Search clients").fill("zzz");
  await expect(
    page.getByText("No clients match. Try another search or filter."),
  ).toBeVisible();
  await expect(page.locator("#rowcount")).toHaveText("0 of 1 clients");
  await page.getByLabel("Reporting date range").selectOption("28");
  await expect(page).toHaveURL(/days=28/);
  await page.goto("/?days=30");
  await expect(page.locator("body")).toContainText("Invalid period");
});
test("Clients and client Overview", async ({ page }) => {
  await login(page, "a@example.test", "/clients/");
  await expect(
    page.getByRole("heading", { name: "Client portfolio", level: 1 }),
  ).toBeVisible();
  await clean(page);
  await page.getByRole("link", { name: "Synthetic Alpha" }).first().click();
  await expect(page).toHaveURL(/\/clients\/synthetic-alpha\/$/);
  await expect(
    page.getByRole("heading", { name: "Synthetic Alpha", level: 1 }),
  ).toBeVisible();
  const snapshot = page.locator(".snapshotgrid");
  await expect(snapshot).toContainText("Not tracked");
  await expect(
    snapshot.locator("a", { hasText: "Google rating" }),
  ).toContainText("4.6 ★");
  await expect(page.getByText("What the numbers mean")).toBeVisible();
  await expect(page.getByText("12 completed · 1 need attention")).toBeVisible();
  await page.getByRole("button", { name: "Client attention items" }).click();
  await expect(page.getByRole("dialog")).toContainText("Requires attention");
  await page.keyboard.press("Escape");
  await clean(page);
});
test("Unbuilt screens share one typed state and show no content", async ({
  page,
}) => {
  await login(page);
  for (const path of [
    "/opportunities/",
    "/reports/",
    "/automations/",
    "/integrations/",
    "/administration/",
    "/administration/users/",
    "/activity/",
    "/attention/",
    "/clients/synthetic-alpha/automations/",
    "/clients/synthetic-alpha/reports/",
    "/clients/synthetic-alpha/settings/",
  ]) {
    await page.goto(path);
    await expect(page.locator("[data-not-built]")).toHaveCount(1);
    await expect(page.locator("[data-not-built]")).toContainText(
      "is not built yet",
    );
  }
  await clean(page);
  expect((await page.goto("/nope/"))?.status()).toBe(404);
  expect((await page.goto("/clients/synthetic-alpha/nope/"))?.status()).toBe(
    404,
  );
});
test("A client user sees only their organization; an administrator sees every client", async ({
  page,
  request,
}) => {
  await login(page);
  await expect(page.locator("[data-client-row]")).toHaveCount(1);
  const switcher = page.getByLabel("Switch client");
  await page.goto("/clients/synthetic-alpha/");
  await expect(switcher.locator("option")).toHaveText([
    "Entire portfolio",
    "Synthetic Alpha",
  ]);
  const own = await page.request.get(
    "/api/command-center/clients/11111111-1111-4111-8111-111111111111/overview/",
  );
  expect(own.status()).toBe(200);
  const foreign = await page.request.get(
    "/api/command-center/clients/99999999-9999-4999-8999-999999999999/overview/",
  );
  expect(foreign.status()).toBe(404);
  expect((await page.goto("/clients/synthetic-gamma/"))?.status()).toBe(404);
  await page.context().clearCookies();
  await login(page, "admin@example.test");
  await expect(page.locator("[data-client-row]")).toHaveCount(3);
  await expect(page.locator(".person")).toContainText("Platform administrator");
  const gamma = page.locator("[data-client-row]", {
    hasText: "Synthetic Gamma",
  });
  await expect(gamma.locator("td").nth(4)).toContainText("Not connected");
  await expect(gamma.locator("td").nth(5)).toContainText("No data");
  await expect(gamma).toContainText("Google not connected");
  // Beta's true zero stays a zero, distinct from unavailable.
  const beta = page.locator("[data-client-row]", { hasText: "Synthetic Beta" });
  await expect(beta.locator("td").nth(4)).toContainText("0");
  await expect(beta.locator("td").nth(3)).toContainText("Not connected");
  await page.goto("/clients/synthetic-gamma/");
  await expect(
    page.getByRole("heading", { name: "Synthetic Gamma", level: 1 }),
  ).toBeVisible();
  await expect(page.locator(".snapshotgrid")).toContainText("No data");
  expect(request).toBeTruthy();
});
test("Responses are private and unauthenticated requests are redirected", async ({
  page,
  request,
}) => {
  const unauth = await request.get("/", { maxRedirects: 0 });
  expect(unauth.status()).toBe(303);
  await login(page);
  const response = await page.request.get(
    "/api/command-center/portfolio/?days=28",
  );
  expect(response.headers()["cache-control"]).toBe("private, no-store");
  expect(
    (await page.request.get("/api/command-center/portfolio/?days=30")).status(),
  ).toBe(400);
});
test("Mobile navigation opens and the table scrolls inside its panel", async ({
  page,
}, info) => {
  test.skip(info.project.name !== "mobile");
  await login(page);
  await page.getByRole("button", { name: "Toggle navigation" }).click();
  await expect(
    page.getByRole("link", { name: /Clients/ }).first(),
  ).toBeVisible();
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth > window.innerWidth,
  );
  expect(overflow).toBe(false);
});
test("A verified factor forces MFA before any page or BFF call, then elevates", async ({
  page,
}) => {
  await login(page, "stepup@example.test", "/clients/");
  // Password only: no shell, no data, straight to the existing /mfa page with the return path.
  await expect(page).toHaveURL(/\/mfa\/\?return=%2Fclients%2F/);
  await expect(page.locator("#sidebar")).toHaveCount(0);
  await expect(page.locator(".person")).toHaveCount(0);
  for (const path of ["/", "/clients/", "/clients/synthetic-alpha/"]) {
    await page.goto(path);
    await expect(page).toHaveURL(/\/mfa\//);
  }
  const bff = await page.request.get("/api/command-center/portfolio/", {
    maxRedirects: 0,
  });
  expect(bff.status()).toBe(403);
  expect(await bff.json()).toMatchObject({ code: "MFA_REQUIRED" });
  await page.goto(`/mfa/?return=${encodeURIComponent("/clients/")}`);
  await page.getByLabel("Authenticator code").fill("123456");
  await page.getByRole("button", { name: "Verify", exact: true }).click();
  await expect(page).toHaveURL(/\/clients\/$/);
  await expect(page.locator(".person")).toContainText("Platform administrator");
  await expect(page.locator("[data-client-row]")).toHaveCount(3);
});

const BUILT = [
  "/clients/synthetic-alpha/local-search/",
  "/clients/synthetic-alpha/reviews/",
  "/clients/synthetic-alpha/website-content/",
  "/clients/synthetic-alpha/leads/",
  "/clients/synthetic-alpha/opportunities/",
  "/clients/synthetic-alpha/integrations/",
];
test("Every sidebar link routes to a built screen or the typed not-built state", async ({
  page,
}) => {
  await login(page);
  const visited: string[] = [];
  async function walk(start: string) {
    await page.goto(start);
    if (page.viewportSize()!.width <= 760)
      await page.getByRole("button", { name: "Toggle navigation" }).click();
    const hrefs = await page
      .locator("#sidebar nav a")
      .evaluateAll((links) =>
        links.map((link) => (link as HTMLAnchorElement).getAttribute("href")!),
      );
    for (const href of hrefs) {
      const response = await page.goto(href);
      expect(response?.status(), href).toBe(200);
      const notBuilt = await page.locator("[data-not-built]").count();
      const heading = await page.locator("main h1").count();
      expect(notBuilt === 1 || heading >= 1, href).toBe(true);
      if (BUILT.includes(href)) expect(notBuilt, href).toBe(0);
      else if (
        href !== "/" &&
        href !== "/clients/" &&
        href !== "/clients/synthetic-alpha/"
      )
        expect(notBuilt, href).toBe(1);
      visited.push(href);
    }
  }
  await walk("/");
  await walk("/clients/synthetic-alpha/");
  expect(visited).toContain("/clients/synthetic-alpha/settings/");
  expect(visited).toContain("/administration/");
  expect(visited.length).toBeGreaterThanOrEqual(17);
});
