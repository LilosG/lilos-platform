import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
const base = "/clients/synthetic-alpha/";
const org = "11111111-1111-4111-8111-111111111111";
const rev = "55555555-5555-4555-8555-555555555555";
const pageId = "44444444-4444-4444-8444-444444444444";
const profileId = "77777777-7777-4777-8777-777777777777";
async function login(
  page: import("@playwright/test").Page,
  email = "a@example.test",
) {
  await page.goto(
    `/login/?return=${encodeURIComponent(base + "integrations/")}`,
  );
  await page.getByLabel("Email", { exact: true }).fill(email);
  await page.getByLabel("Password", { exact: true }).fill("synthetic-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
}
test("Integrations canonical states -> discover -> explicit mapping -> sync", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await login(page);
  await expect(
    page.getByRole("heading", { name: "Integrations", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("reconnect_required", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText(/PROVIDER_RATE_LIMITED/)).toBeVisible();
  await expect(
    page.getByText(/Mapping: mapped · Freshness: stale/),
  ).toBeVisible();
  await page
    .getByRole("button", {
      name: "Discover Search Console properties",
      exact: true,
    })
    .click();
  await expect(
    page.getByRole("button", {
      name: "Confirm sc-domain:synthetic.example.invalid",
      exact: true,
    }),
  ).toBeVisible();
  const mapReload = page.waitForNavigation({ waitUntil: "domcontentloaded" });
  const mapped = page.waitForRequest(
    (r) =>
      r.url().endsWith("search-console/properties/map/") &&
      r.method() === "POST",
  );
  await page
    .getByRole("button", {
      name: "Confirm sc-domain:synthetic.example.invalid",
      exact: true,
    })
    .click();
  await mapReload;
  expect((await mapped).postDataJSON()).toEqual({
    website_id: org,
    external_property_id: "sc-domain:synthetic.example.invalid",
    property_type: "domain",
  });
  await expect(
    page.getByRole("heading", { name: "Integrations", exact: true }),
  ).toBeVisible();
  const syncReload = page.waitForNavigation({ waitUntil: "domcontentloaded" });
  const sync = page.waitForRequest((r) =>
    r.url().includes(`/search-properties/${rev}/sync/`),
  );
  await page
    .getByRole("button", { name: "Queue Search Console sync", exact: true })
    .click();
  await syncReload;
  expect((await sync).postDataJSON()).toEqual({ days: 28 });
  await expect(
    page.getByRole("heading", { name: "Integrations", exact: true }),
  ).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.screenshot({
    path: test.info().outputPath("integrations.png"),
    fullPage: true,
  });
  expect(errors).toEqual([]);
});
test("Local Search all tabs -> page intelligence and scoped GBP posts", async ({
  page,
}) => {
  await login(page);
  await page
    .getByRole("link", { name: "Open Local Search", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Local Search", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText(/Google authorization: reconnect_required/),
  ).toBeVisible();
  await page.getByRole("link", { name: "Rankings", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Run rank scan unavailable" }),
  ).toBeDisabled();
  await page.getByRole("link", { name: "Search Console", exact: true }).click();
  await expect(
    page.getByText("synthetic brunch", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText(/Quality: partial/)).toBeVisible();
  await expect(
    page.getByText(/Comparison: 2026-08-07 – 2026-09-04 \(28 days\)/),
  ).toBeVisible();
  await page.getByRole("link", { name: "Pages", exact: true }).click();
  await page
    .getByRole("link", { name: "Inspect page intelligence", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Page intelligence", exact: true }),
  ).toBeVisible();
  await expect(page.getByText("Unavailable", { exact: true })).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.getByRole("link", { name: "All pages", exact: true }).click();
  await page.getByRole("link", { name: "Technical", exact: true }).click();
  await expect(
    page.getByText("missing_meta_description", { exact: true }),
  ).toBeVisible();
  const crawlReload = page.waitForNavigation({ waitUntil: "domcontentloaded" });
  const crawl = page.waitForRequest((r) =>
    r.url().endsWith(`/seo/websites/${org}/check/`),
  );
  await page
    .getByRole("button", { name: "Run website check", exact: true })
    .click();
  await crawlReload;
  expect((await crawl).postDataJSON().idempotency_key).toMatch(
    /^[0-9a-f-]{36}$/,
  );
  await expect(
    page.getByRole("heading", { name: "Technical findings", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("link", { name: "Google Business Profile", exact: true })
    .click();
  await expect(
    page.getByRole("heading", {
      name: "GBP performance unavailable",
      exact: true,
    }),
  ).toBeVisible();
  await page
    .getByRole("link", { name: "View profile and posts", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Business Profile", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", {
      name: "Approve exact post revision 1",
      exact: true,
    }),
  ).toBeDisabled();
  await page
    .getByLabel("Post content", { exact: true })
    .fill("Exact synthetic draft");
  const draftReload = page.waitForNavigation({ waitUntil: "domcontentloaded" });
  const draft = page.waitForRequest((r) =>
    r.url().endsWith(`/locations/${profileId}/posts/`),
  );
  await page
    .getByRole("button", { name: "Save post draft", exact: true })
    .click();
  await draftReload;
  expect((await draft).postDataJSON()).toEqual({
    post_type: "standard",
    content: "Exact synthetic draft",
  });
  await expect(
    page.getByRole("heading", { name: "Business Profile", exact: true }),
  ).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
});
test("Phase 2 tenant and cache isolation plus fixed OAuth return resolution", async ({
  page,
  request,
}) => {
  await login(page);
  const response = await page.goto(base + "local-search/pages/");
  expect(response?.headers()["cache-control"]).toBe("private, no-store");
  await page.goto(`/integrations/?org=${org}&connected=1`);
  await expect(page).toHaveURL(new RegExp(base + "integrations/"));
  if ((page.viewportSize()?.width ?? 1440) < 700) {
    const menu = page.getByRole("button", { name: "Toggle navigation" });
    await menu.click();
    await expect(menu).toHaveAttribute("aria-expanded", "true");
  }
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await login(page, "b@example.test");
  for (const path of [
    base + "integrations/",
    base + "local-search/",
    base + `local-search/pages/${org}/${pageId}/`,
    base + `local-search/profiles/${org}/${profileId}/`,
  ]) {
    const denied = await page.goto(path);
    expect(denied?.status()).toBe(404);
    expect(await page.content()).not.toContain("Synthetic menu");
  }
  const foreign = await request.get(
    `/api/organizations/${org}/command-center/local-search/`,
  );
  expect(foreign.status()).toBe(401);
  expect(foreign.headers()["cache-control"]).toBe("private, no-store");
});
