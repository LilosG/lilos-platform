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
    page.getByRole("heading", { name: "Website overview", exact: true }),
  ).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.getByRole("link", { name: "Pages", exact: true }).click();
  await page
    .getByRole("link", { name: "Inspect page", exact: true })
    .first()
    .click();
  await expect(
    page.getByRole("heading", { name: "Page repository mapping" }),
  ).toBeVisible();
  await expect(page.getByText(/SITE_MAPPING_REQUIRED/)).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.goto(base + "technical/");
  await expect(
    page.getByRole("heading", { name: "Technical findings" }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Conversions", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Conversion paths unavailable" }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Content", exact: true }).click();
  await page.getByLabel("Title", { exact: true }).fill("Synthetic new item");
  await page.getByLabel("Slug", { exact: true }).fill("synthetic-new-item");
  await page.getByLabel("Content type", { exact: true }).fill("blog");
  await page
    .getByRole("button", { name: "Create content item", exact: true })
    .click();
  await expect(page).toHaveURL(base + `content/${fixtures.detail.id}/`);

  await expect(
    page.getByRole("heading", { name: "Immutable revisions" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Approve exact revision 1" }),
  ).toBeDisabled();
  await page
    .getByLabel("Body", { exact: true })
    .fill("Synthetic new immutable revision.");
  await page
    .locator('[data-content-form="revision"] input[name="fact"]')
    .first()
    .check();
  const request = page.waitForRequest(
    (r) => r.method() === "POST" && r.url().endsWith("/revisions/"),
  );
  await Promise.all([
    page.waitForEvent("load"),
    page.getByRole("button", { name: "Save new content revision" }).click(),
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
  await page.getByRole("button", { name: "Approve exact revision 1" }).click();
  await expect(
    page.getByRole("heading", { name: "Revision 1 · awaiting_client" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Approve exact revision 1" }).click();
  await expect(
    page.getByRole("heading", { name: "Revision 1 · approved" }),
  ).toBeVisible();
  const publish = page.waitForRequest(
    (r) => r.method() === "POST" && r.url().endsWith("/publish/"),
  );
  await page.getByRole("button", { name: "Dispatch approved content" }).click();
  expect((await publish).postDataJSON().publishing_target_id).toBe(
    fixtures.detail.publishing_targets[0].id,
  );
  await expect(
    page.getByRole("heading", { name: "Publication: pull_request_created" }),
  ).toBeVisible();
  await expect(page.getByText(/Checks\/build: checks_running/)).toBeVisible();
  await expect(page.getByText(/Deployment: Not confirmed/)).toBeVisible();
  await expect(
    page.getByText(/Live verification: Not confirmed/),
  ).toBeVisible();
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
