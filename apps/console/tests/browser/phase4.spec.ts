import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import fixtures from "../fixtures/phase4.json" with { type: "json" };
const base = "/clients/synthetic-alpha/website-content/";
async function login(page: import("@playwright/test").Page) {
  await page.goto(`/login/?return=${encodeURIComponent(base)}`);
  await page.getByLabel("Email", { exact: true }).fill("a@example.test");
  await page.getByLabel("Password", { exact: true }).fill("synthetic-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
}
test("Website five tabs, page evidence, editor and accessibility", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await login(page);
  await expect(
    page.getByRole("heading", { name: "Website & Content", level: 1 }),
  ).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.getByRole("link", { name: "Pages", exact: true }).click();
  await page
    .locator("[data-page-row]")
    .first()
    .getByRole("link")
    .first()
    .click();
  await expect(page.locator("[data-page-mapping] .badge")).toHaveText(
    "Repository not linked",
  );
  await expect(page.getByText(/SITE_MAPPING_REQUIRED/)).toHaveCount(0);
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.goto(base + "technical/");
  await expect(
    page.getByRole("heading", { name: "Technical findings" }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Conversions", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Conversion paths are not tracked yet" }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Content", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: /Articles and guides/ }),
  ).toBeVisible();
  await page.getByRole("button", { name: "New content" }).click();
  await page
    .getByLabel("What should it be about?")
    .fill("write a blog about synthetic things");
  const compose = page.waitForRequest(
    (r) => r.method() === "POST" && r.url().endsWith("/content/compose/"),
  );
  await Promise.all([
    page.waitForEvent("load"),
    page.getByRole("button", { name: "Write it" }).click(),
  ]);
  expect((await compose).postDataJSON()).toMatchObject({
    prompt: "write a blog about synthetic things",
    content_type: null,
  });

  await page.goto(base + `content/${fixtures.detail.id}/`);
  await expect(
    page.getByRole("heading", { name: "Draft review" }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Approve…" })).toBeDisabled();
  await page.getByRole("button", { name: "Edit", exact: true }).click();
  await page
    .getByLabel("Article", { exact: true })
    .fill("Synthetic new immutable revision.");
  const request = page.waitForRequest(
    (r) => r.method() === "POST" && r.url().endsWith("/revisions/"),
  );
  await Promise.all([
    page.waitForEvent("load"),
    page.getByRole("button", { name: "Save as a new revision" }).click(),
  ]);
  expect((await request).postDataJSON()).toMatchObject({
    body: "Synthetic new immutable revision.",
    created_by_type: "user",
  });
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.screenshot({
    path: test.info().outputPath("website-content-editor.png"),
    fullPage: true,
  });
  expect(errors).toEqual([]);
});
test("Website exact MFA approval and publication remain PR-open with no deployment/live success", async ({
  page,
}) => {
  await login(page);
  const detail = base + `content/${fixtures.detail.id}/`;
  await page.goto(`/mfa/?return=${encodeURIComponent(detail)}`);
  const enroll = page.getByRole("button", { name: "Set up authenticator" });
  if (await enroll.count()) await enroll.click();
  await page.getByLabel("Authenticator code").fill("123456");
  await page.getByRole("button", { name: "Verify", exact: true }).click();
  await page.getByRole("button", { name: "Approve…" }).click();
  await expect(page.locator("[data-exact-change]")).toContainText(
    "src/content/blog/synthetic-article.mdx",
  );
  await page
    .locator("#content-approval")
    .getByRole("button", { name: "Approve draft" })
    .click();
  await expect(page.locator(".badge").first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Approve…" })).toBeEnabled();
  await page.getByRole("button", { name: "Approve…" }).click();
  await page
    .locator("#content-approval")
    .getByRole("button", {
      name: "Approve for publishing",
    })
    .click();
  await expect(
    page.getByRole("button", { name: "Publish approved draft" }),
  ).toBeEnabled();
  const publish = page.waitForRequest(
    (r) => r.method() === "POST" && r.url().endsWith("/publish/"),
  );
  await page.getByRole("button", { name: "Publish approved draft" }).click();
  expect((await publish).postDataJSON().publishing_target_id).toBe(
    fixtures.detail.publishing_targets[0].id,
  );
  const publication = page.locator("[data-publication]");
  await expect(publication.locator(".badge")).toHaveText("Checking");
  await publication.getByText("Details").click();
  await expect(publication).toContainText("Not confirmed");
  await expect(publication).not.toContainText(
    /pull_request_created|checks_running/,
  );
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
});
test("Website closed BFF tenant site auth CSRF and cache", async ({ page }) => {
  const org = fixtures.workspace.organization_id;
  const path = `/api/organizations/${org}/command-center/website-content/`;
  expect((await page.request.get(path)).status()).toBe(401);
  await login(page);
  const result = await page.request.get(path);
  expect(result.status()).toBe(200);
  expect(result.headers()["cache-control"]).toBe("private, no-store");
  expect(
    (
      await page.request.get(`${path}?website_id=${fixtures.detail.id}`)
    ).status(),
  ).toBe(404);
  expect(
    (
      await page.request.get(
        path.replace(org, "22222222-2222-4222-8222-222222222222"),
      )
    ).status(),
  ).toBe(404);
  expect(
    (
      await page.request.post(
        `/api/organizations/${org}/content-operations/${fixtures.detail.id}/publish/`,
        { data: { idempotency_key: "phase4-forged" } },
      )
    ).status(),
  ).toBe(403);
});
