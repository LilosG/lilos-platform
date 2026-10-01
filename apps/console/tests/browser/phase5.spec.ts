import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import fixture from "../fixtures/phase5.json" with { type: "json" };
const base = "/clients/synthetic-alpha/leads/";
const upstream = "http://127.0.0.1:4455/test/leads-scenario";
async function login(page: import("@playwright/test").Page) {
  await page.goto(`/login/?return=${encodeURIComponent(base)}`);
  await page.getByLabel("Email", { exact: true }).fill("a@example.test");
  await page.getByLabel("Password", { exact: true }).fill("synthetic-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Lead inventory", exact: true }),
  ).toBeVisible();
}
test.beforeEach(async ({ request }) => {
  await request.post(upstream, { data: { mode: "inventory" } });
});
test("Leads inventory, detail, outcomes and accessibility", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await login(page);
  await expect(
    page.getByText("Unknown outcome", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText(/synthetic_test_provider/).first()).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.getByRole("link", { name: "Outcomes", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Measured conversion outcomes" }),
  ).toBeVisible();
  await page.getByRole("link", { name: "View lead", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Lead detail", exact: true }),
  ).toBeVisible();
  await expect(page.getByText(/Unknown outcome/)).toBeVisible();
  await expect(
    page.getByText(/Campaign \/ landing-page attribution: unavailable/),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "email · planned" }),
  ).toBeVisible();
  await expect(page.getByText(/Delivered: Unconfirmed/)).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Record consent", exact: true }),
  ).toBeDisabled();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.screenshot({
    path: test.info().outputPath("leads-detail.png"),
    fullPage: true,
  });
  await page.getByRole("link", { name: "Close details" }).press("Escape");
  await expect(page).toHaveURL(new RegExp("/leads/\\?location_id="));
  expect(errors).toEqual([]);
});
test("Leads canonical notes, status and recorded conversion remain distinct from downstream outcomes", async ({
  page,
}) => {
  await login(page);
  await page.getByRole("link", { name: "View lead", exact: true }).click();
  await expect(page.locator('[data-lead-form="note"]')).not.toHaveAttribute(
    "inert",
  );
  await page
    .getByLabel("Note", { exact: true })
    .fill("Measured follow-up evidence");
  const request = page.waitForRequest(
    (r) => r.method() === "POST" && r.url().endsWith("/notes/"),
  );
  await Promise.all([
    page.waitForEvent("load"),
    page.getByRole("button", { name: "Add note", exact: true }).click(),
  ]);
  expect((await request).postDataJSON()).toEqual({
    body: "Measured follow-up evidence",
  });
  await expect(page.getByText(/Measured follow-up evidence/)).toBeVisible();
  await page.getByLabel("Status", { exact: true }).selectOption("contacted");
  await Promise.all([
    page.waitForEvent("load"),
    page.getByRole("button", { name: "Save lead status" }).click(),
  ]);
  await expect(page.getByText(/Lead status: contacted/)).toBeVisible();
  await expect(page.getByText(/Unknown outcome/)).toBeVisible();
  await Promise.all([
    page.waitForEvent("load"),
    page
      .getByRole("button", { name: "Record lead conversion", exact: true })
      .click(),
  ]);
  await expect(
    page.getByText(/Recorded lead conversion · Lead status: converted/),
  ).toBeVisible();
  await expect(
    page.getByText(
      /Completed reservations, sales, booked jobs and revenue: unavailable/,
    ),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Record lead conversion", exact: true }),
  ).toBeDisabled();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
});
test("Leads zero, unavailable and source error remain explicit", async ({
  page,
  request,
}) => {
  await login(page);
  await request.post(upstream, { data: { mode: "zero" } });
  await page.reload();
  await expect(
    page.getByText("No recorded leads in this scope.", { exact: true }),
  ).toBeVisible();
  await expect(
    page.locator('[aria-label="Persisted lead metrics"] strong').first(),
  ).toHaveText("0");
  await request.post(upstream, { data: { mode: "unavailable" } });
  await page.reload();
  await expect(
    page.locator('[aria-label="Persisted lead metrics"] strong').first(),
  ).toHaveText("Unavailable");
  await request.post(upstream, { data: { mode: "error" } });
  await page.reload();
  await expect(page.getByRole("alert")).toContainText(
    "temporarily unavailable",
  );
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
});
test("Leads wrong tenant/location, auth, BFF, CSRF and private cache", async ({
  page,
  request,
}) => {
  const unauth = await request.get(base, { maxRedirects: 0 });
  expect(unauth.status()).toBe(303);
  await login(page);
  const api = `/api/organizations/${fixture.workspace.organization_id}/command-center/leads/`;
  const data = await page.request.get(api);
  expect(data.headers()["cache-control"]).toBe("private, no-store");
  expect((await page.request.get(api + "?location_id=bad")).status()).toBe(400);
  const wrongLocation = await page.request.get(
    api + `?location_id=${fixture.workspace.organization_id}`,
  );
  expect(wrongLocation.status()).toBe(404);
  const forged = await page.request.post(
    `/api/organizations/${fixture.workspace.organization_id}/leads/${fixture.detail.lead.id}/convert/`,
    { data: {}, headers: { Origin: "https://evil.test" } },
  );
  expect(forged.status()).toBe(403);
  await page.goto(base + fixture.detail.lead.id + "/");
  await expect(
    page.getByRole("heading", { name: "Lead detail", exact: true }),
  ).toBeVisible();
  await page.context().clearCookies();
  await page.goto(`/login/?return=${encodeURIComponent(base)}`);
  await page.getByLabel("Email", { exact: true }).fill("b@example.test");
  await page.getByLabel("Password", { exact: true }).fill("synthetic-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.goto(base + fixture.detail.lead.id + "/");
  await expect(
    page.getByText("Client not found", { exact: true }),
  ).toBeVisible();
  expect((await page.request.get(api)).status()).toBe(404);
});

test("Leads assignment, tasks, AAL2 consent and communication use canonical bodies", async ({
  page,
}) => {
  await login(page);
  await page.getByRole("link", { name: "View lead", exact: true }).click();
  await expect(page.locator('[data-lead-form="assign"]')).not.toHaveAttribute(
    "inert",
  );
  await page
    .getByLabel("Teammate", { exact: true })
    .selectOption(fixture.workspace.organization_id);
  await Promise.all([
    page.waitForEvent("load"),
    page.getByRole("button", { name: "Assign lead", exact: true }).click(),
  ]);
  await expect(
    page.getByText("Assignee: Synthetic operator", { exact: true }),
  ).toBeVisible();
  await page
    .getByLabel("Task title", { exact: true })
    .fill("Canonical follow-up");
  await Promise.all([
    page.waitForEvent("load"),
    page.getByRole("button", { name: "Create task", exact: true }).click(),
  ]);
  await expect(
    page.getByRole("heading", { name: "Canonical follow-up · open" }),
  ).toBeVisible();
  await Promise.all([
    page.waitForEvent("load"),
    page.getByRole("button", { name: "Complete task", exact: true }).click(),
  ]);
  await expect(
    page.getByRole("heading", { name: "Canonical follow-up · completed" }),
  ).toBeVisible();
  await page
    .getByRole("link", { name: "Verify authenticator for protected actions" })
    .click();
  const enroll = page.getByRole("button", { name: "Set up authenticator" });
  if (await enroll.count()) await enroll.click();
  await page.getByLabel("Authenticator code").fill("123456");
  await page.getByRole("button", { name: "Verify", exact: true }).click();
  await page
    .getByLabel("Consent status", { exact: true })
    .selectOption("granted");
  await page
    .getByLabel("Evidence source", { exact: true })
    .fill("canonical_form");
  await page
    .getByLabel("Disclosure version", { exact: true })
    .fill("version-1");
  await page
    .getByLabel("Evidence reference", { exact: true })
    .fill("canonical-submission");
  await page
    .getByLabel("Captured at (ISO timestamp with timezone)", { exact: true })
    .fill("2026-10-01T00:00:00Z");
  await Promise.all([
    page.waitForEvent("load"),
    page.getByRole("button", { name: "Record consent", exact: true }).click(),
  ]);
  await expect(
    page.getByText(/email · transactional_email · granted/),
  ).toBeVisible();
  await page
    .getByLabel("Message reference", { exact: true })
    .fill("canonical-message-reference");
  const request = page.waitForRequest(
    (r) => r.method() === "POST" && r.url().endsWith("/communications/"),
  );
  await Promise.all([
    page.waitForEvent("load"),
    page
      .getByRole("button", { name: "Plan communication", exact: true })
      .click(),
  ]);
  expect((await request).postDataJSON()).toMatchObject({
    channel: "email",
    consent_type: "transactional_email",
    message_reference: "canonical-message-reference",
    idempotency_key: expect.any(String),
  });
  await expect(
    page.getByRole("heading", { name: "email · planned" }).last(),
  ).toBeVisible();
  await expect(page.getByText(/Delivered: Unconfirmed/).last()).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
});
