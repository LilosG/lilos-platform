import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import fixture from "../fixtures/phase6.json" with { type: "json" };
const base = "/clients/synthetic-alpha/automations/";
const scenario = `http://127.0.0.1:${process.env.CONSOLE_TEST_UPSTREAM_PORT ?? 4455}/test/automations-scenario`;
async function login(page: import("@playwright/test").Page) {
  await page.goto(`/login/?return=${encodeURIComponent(base)}`);
  await page.getByLabel("Email", { exact: true }).fill("a@example.test");
  await page.getByLabel("Password", { exact: true }).fill("synthetic-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Upcoming Important Runs", exact: true }),
  ).toBeVisible();
}
test.beforeEach(async ({ request }) => {
  await request.post(scenario, { data: { mode: "inventory" } });
});
test("Automations exception-first overview, run history, recovery and accessibility", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await login(page);
  await expect(
    page.getByRole("heading", { name: "Recent Meaningful Outcomes" }),
  ).toBeVisible();
  await expect(
    page.getByText(/Worker and scheduler health: unavailable/),
  ).toBeVisible();
  await expect(
    page.getByText("partial · partially_completed", { exact: false }),
  ).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page
    .getByRole("link", { name: "Investigate", exact: true })
    .first()
    .click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(
    page.getByText(/Generic manual retry is unavailable/),
  ).toBeVisible();
  await expect(page.getByText(/Attempts 3 \/ 3/)).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page
    .getByText("Execution evidence and audit history", { exact: true })
    .click();
  await expect(page.getByText(/canonical-phase6-key/)).toBeVisible();
  await page.screenshot({
    path: test.info().outputPath("automations-run.png"),
    fullPage: true,
  });
  await page.getByRole("link", { name: "Close details" }).press("Escape");
  await expect(page).toHaveURL(new RegExp("/automations/all/"));
  expect(errors).toEqual([]);
});
test("Automations schedules pause/resume, unscheduled and queued execution", async ({
  page,
}) => {
  await login(page);
  await page
    .getByRole("link", { name: "All Automations", exact: true })
    .first()
    .click();
  await expect(
    page.getByText("Unscheduled", { exact: true }).first(),
  ).toBeVisible();
  await expect(page.getByText(/Disabled \/ disabled/)).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Pause schedule", exact: true }),
  ).not.toHaveAttribute("inert");
  const sent = page.waitForRequest((r) => r.method() === "PATCH");
  await Promise.all([
    page.waitForEvent("load"),
    page.getByRole("button", { name: "Pause schedule", exact: true }).click(),
  ]);
  expect((await sent).postDataJSON()).toEqual({ status: "paused" });
  await expect(
    page.getByRole("button", { name: "Resume schedule", exact: true }),
  ).toHaveCount(2);
  await Promise.all([
    page.waitForEvent("load"),
    page
      .getByRole("button", { name: "Resume schedule", exact: true })
      .first()
      .click(),
  ]);
  await expect(
    page.getByRole("button", { name: "Pause schedule", exact: true }),
  ).toBeVisible();
  const run = page.waitForRequest(
    (r) => r.method() === "POST" && r.url().endsWith("/gbp.sync/runs/"),
  );
  await Promise.all([
    page.waitForEvent("load"),
    page
      .getByRole("button", {
        name: "Run now: Business Profile sync",
        exact: true,
      })
      .click(),
  ]);
  expect((await run).postDataJSON()).toMatchObject({
    input_document: {},
    execute: true,
  });
  await expect(
    page.getByRole("cell", { name: "queued Job: queued", exact: true }).first(),
  ).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.screenshot({
    path: test.info().outputPath("automations-all.png"),
    fullPage: true,
  });
});
test("Automations unavailable/error, scope, CSRF and private cache", async ({
  page,
  request,
}) => {
  await login(page);
  await request.post(scenario, { data: { mode: "unavailable" } });
  await page.reload();
  await expect(
    page.getByText("Schedules unavailable: read permission required.", {
      exact: true,
    }),
  ).toBeVisible();
  await request.post(scenario, { data: { mode: "error" } });
  await page.reload();
  await expect(page.getByRole("alert")).toContainText(
    "temporarily unavailable",
  );
  const path = `/api/organizations/${fixture.workspace.organization_id}/command-center/automations/`;
  const response = await page.request.get(path);
  expect(response.headers()["cache-control"]).toBe("private, no-store");
  expect(
    (await page.request.get(path + "?url=https://evil.test")).status(),
  ).toBe(400);
  expect(
    (
      await page.request.patch(
        `/api/organizations/${fixture.workspace.organization_id}/workflows/schedules/${fixture.workspace.schedules[0].id}/`,
        {
          data: { status: "paused" },
          headers: { Origin: "https://evil.test" },
        },
      )
    ).status(),
  ).toBe(403);
  expect(
    (
      await page.request.get(
        "/api/organizations/22222222-2222-4222-8222-222222222222/command-center/automations/",
      )
    ).status(),
  ).toBe(404);
  const other = await page.request.get("/clients/synthetic-beta/automations/");
  expect(other.status()).toBe(404);
  expect(await other.text()).not.toContain("Business Profile sync");
});

test("Automations explicitly configured schedule and canonical agent control", async ({
  page,
  request,
}) => {
  await login(page);
  await page
    .getByRole("link", { name: "All Automations", exact: true })
    .first()
    .click();
  await expect(
    page.locator('[data-automation-form="schedule"]'),
  ).not.toHaveAttribute("inert");
  await page
    .getByLabel("Schedule key", { exact: true })
    .fill("phase6-explicit-schedule");
  await page.getByLabel("Cron expression", { exact: true }).fill("0 9 * * *");
  await page.getByLabel("Timezone", { exact: true }).fill("UTC");
  await page
    .getByLabel("First dispatch (ISO timestamp with timezone)", { exact: true })
    .fill("2026-10-04T09:00:00Z");
  const created = page.waitForRequest(
    (r) => r.method() === "POST" && r.url().endsWith("/workflows/schedules/"),
  );
  await Promise.all([
    page.waitForEvent("load"),
    page.getByRole("button", { name: "Create schedule", exact: true }).click(),
  ]);
  expect((await created).postDataJSON()).toEqual({
    workflow_key: "gbp.sync",
    key: "phase6-explicit-schedule",
    cron_expression: "0 9 * * *",
    timezone: "UTC",
    next_run_at: "2026-10-04T09:00:00Z",
    location_id: null,
  });
  await expect(
    page.getByRole("heading", { name: "New canonical schedule", exact: true }),
  ).toBeVisible();
  await request.post(scenario, { data: { mode: "agent" } });
  await page.goto(base + `runs/${fixture.detail.run.id}/`);
  await expect(
    page.locator('[data-automation-form="steer"]'),
  ).not.toHaveAttribute("inert");
  await page
    .getByLabel("Steering instruction", { exact: true })
    .fill("Inspect the latest scoped evidence");
  const steer = page.waitForRequest(
    (r) => r.url().endsWith("/steer/") && r.method() === "POST",
  );
  await Promise.all([
    page.waitForEvent("load"),
    page.getByRole("button", { name: "Send instruction", exact: true }).click(),
  ]);
  expect((await steer).postDataJSON()).toEqual({
    text: "Inspect the latest scoped evidence",
  });
  await expect(
    page.getByRole("button", { name: "Stop agent", exact: true }),
  ).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
});
