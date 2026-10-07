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
  await page.locator('body[data-app-ready="true"]').waitFor();
}
test("Reviews inbox, unavailable requests, exact response draft, audit and accessibility", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await login(page);
  await expect(
    page.getByRole("heading", { name: /Review inbox/ }),
  ).toBeVisible();
  await page.getByRole("button", { name: /Review source status/ }).click();
  const source = page.getByRole("dialog");
  await expect(source).toContainText("Google connection");
  await expect(source).toContainText("Reconnect Google");
  await expect(source).toContainText("Out of date");
  await source.getByRole("button", { name: "Close", exact: true }).click();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.screenshot({
    path: test.info().outputPath("reviews-inbox.png"),
    fullPage: true,
  });
  await page
    .getByRole("link", { name: "Review requests", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Review requests are not tracked yet" }),
  ).toBeVisible();
  await page.goto(detail);
  await expect(
    page.getByRole("heading", { name: "Reply to Jordan Sample" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Approve this response" }),
  ).toBeDisabled();
  await expect(page.getByText("Facts this response may use")).toHaveCount(0);
  await expect(page.getByRole("checkbox")).toHaveCount(0);
  await page
    .getByLabel("Edit the response", { exact: true })
    .fill("Thanks for this synthetic visit.");
  const request = page.waitForRequest(
    (r) => r.method() === "POST" && r.url().endsWith("/responses/"),
  );
  await Promise.all([
    page.waitForEvent("load"),
    page.getByRole("button", { name: "Save changes" }).click(),
  ]);
  const saved = (await request).postDataJSON();
  expect(saved).toMatchObject({
    review_revision_id: fixtures.detail.review.revision_id,
    generated_by_type: "user",
  });
  expect(saved).not.toHaveProperty("approved_fact_revision_ids");
  await expect(
    page.getByRole("heading", { name: "Reply to Jordan Sample" }),
  ).toBeVisible();
  await page.getByText("Activity", { exact: true }).click();
  await expect(page.getByText("Response drafted").first()).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.screenshot({
    path: test.info().outputPath("review-response.png"),
    fullPage: true,
  });
  expect(errors).toEqual([]);
});
test("A reply is generated in one click with no facts to choose", async ({
  page,
}) => {
  await login(page);
  await page.goto(detail);
  const request = page.waitForRequest(
    (r) => r.method() === "POST" && r.url().endsWith("/responses/ai-draft/"),
  );
  await Promise.all([
    page.waitForEvent("load"),
    page.getByRole("button", { name: "Generate a response" }).click(),
  ]);
  const body = (await request).postDataJSON();
  expect(body).toMatchObject({
    review_revision_id: fixtures.detail.review.revision_id,
  });
  expect(body).not.toHaveProperty("approved_fact_revision_ids");
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
  await page.getByRole("button", { name: "Approve this response" }).click();
  await expect(
    page.getByRole("region", { name: "Current response" }),
  ).toContainText("Approved");
  const dispatch = page.waitForRequest(
    (r) => r.method() === "POST" && r.url().endsWith("/publish/"),
  );
  await page.getByRole("button", { name: "Publish to Google" }).click();
  expect((await dispatch).postDataJSON()).toEqual({
    idempotency_key: `console-review-${fixtures.detail.responses[0].id}`,
  });
  await expect(
    page.getByRole("region", { name: "Current response" }),
  ).toContainText("Publishing");
  await expect(
    page.getByRole("button", { name: "Publish to Google" }),
  ).toBeDisabled();
});
