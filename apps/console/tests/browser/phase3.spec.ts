import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import fixtures from "../fixtures/phase3.json" with { type: "json" };
const base = "/clients/synthetic-alpha/reviews/";
const detail =
  base +
  `locations/${fixtures.detail.location_id}/${fixtures.detail.review.id}/`;
async function login(page: import("@playwright/test").Page) {
  await page.goto(`/login/?return=${encodeURIComponent(base)}`);
  await page.getByLabel("Email", { exact: true }).fill("a@example.test");
  await page.getByLabel("Password", { exact: true }).fill("synthetic-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
}
test("Reviews inbox, unavailable requests, exact response draft, audit and accessibility", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await login(page);
  await expect(
    page.getByRole("heading", { name: "Review inbox" }),
  ).toBeVisible();
  await expect(
    page.getByText(/Freshness:\s*stale\s*·\s*Quality:\s*partial/),
  ).toBeVisible();
  await expect(
    page.getByText(/Google authorization: reconnect_required/),
  ).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.screenshot({
    path: test.info().outputPath("reviews-inbox.png"),
    fullPage: true,
  });
  await page
    .getByRole("link", { name: "Review requests", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Review requests unavailable" }),
  ).toBeVisible();
  await page.goto(detail);
  await expect(
    page.getByRole("heading", { name: "Review response", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Approve exact response revision 1" }),
  ).toBeDisabled();
  await page.getByLabel("business.name", { exact: false }).check();
  await page
    .getByLabel("Response", { exact: true })
    .fill("Thanks for this synthetic visit.");
  const request = page.waitForRequest(
    (r) => r.method() === "POST" && r.url().endsWith("/responses/"),
  );
  await Promise.all([
    page.waitForEvent("load"),
    page.getByRole("button", { name: "Save new response revision" }).click(),
  ]);
  expect((await request).postDataJSON()).toMatchObject({
    review_revision_id: fixtures.detail.review.revision_id,
    generated_by_type: "user",
    approved_fact_revision_ids: [fixtures.detail.facts[0].id],
  });
  await expect(
    page.getByRole("heading", { name: "Review response", exact: true }),
  ).toBeVisible();
  await page.getByText("Response audit history", { exact: true }).click();
  await expect(
    page.getByText(/Canonical synthetic draft/).first(),
  ).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.screenshot({
    path: test.info().outputPath("review-response.png"),
    fullPage: true,
  });
  expect(errors).toEqual([]);
});
test("Reviews authenticated reads enforce tenant, location, CSRF and private cache", async ({
  page,
}) => {
  await login(page);
  const org = fixtures.workspace.organization_id;
  const response = await page.request.get(
    `/api/organizations/${org}/command-center/reviews/?location_id=${fixtures.workspace.location_id}`,
  );
  expect(response.status()).toBe(200);
  expect(response.headers()["cache-control"]).toBe("private, no-store");
  expect(
    (
      await page.request.get(
        `/api/organizations/${org}/command-center/reviews/?location_id=${org}`,
      )
    ).status(),
  ).toBe(404);
  expect(
    (
      await page.request.get(
        "/api/organizations/22222222-2222-4222-8222-222222222222/command-center/reviews/",
      )
    ).status(),
  ).toBe(404);
  expect(
    (
      await page.request.post(
        `/api/organizations/${org}/locations/${fixtures.workspace.location_id}/reviews/ingest/`,
        { data: {} },
      )
    ).status(),
  ).toBe(403);
});

test("Reviews MFA exact approval then canonical dispatch stays queued", async ({
  page,
}) => {
  await login(page);
  await page.goto(`/mfa/?return=${encodeURIComponent(detail)}`);
  const enroll = page.getByRole("button", { name: "Set up authenticator" });
  if (await enroll.count()) await enroll.click();
  await page.getByLabel("Authenticator code").fill("123456");
  await page.getByRole("button", { name: "Verify", exact: true }).click();
  await expect(page).toHaveURL(new RegExp(detail));
  await page
    .getByRole("button", { name: "Approve exact response revision 1" })
    .click();
  await expect(
    page.getByRole("heading", { name: "Response revision 1 · approved" }),
  ).toBeVisible();
  const dispatch = page.waitForRequest(
    (r) => r.method() === "POST" && r.url().endsWith("/publish/"),
  );
  await page
    .getByRole("button", { name: "Dispatch approved response revision 1" })
    .click();
  expect((await dispatch).postDataJSON()).toEqual({
    idempotency_key: `console-review-${fixtures.detail.responses[0].id}`,
  });
  await expect(
    page.getByRole("heading", { name: "Response revision 1 · publishing" }),
  ).toBeVisible();
  await expect(page.getByText(/Workflow: queued/)).toBeVisible();
  await expect(
    page.getByText(/Published\/read-back: Not confirmed/),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Dispatch approved response revision 1" }),
  ).toBeDisabled();
});
