import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
const sim = "http://127.0.0.1:4455/test";
async function scenario(mode: string) {
  const response = await fetch(`${sim}/admin-scenario`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode }),
  });
  expect(response.ok).toBe(true);
}
async function requests() {
  return (await (await fetch(`${sim}/admin-requests`)).json()).requests as {
    path: string;
    organization_id?: string;
    invitation_id?: string;
    body: Record<string, unknown>;
  }[];
}
async function login(page: Page, who: string, target: string) {
  await page.goto(`/login/?return=${encodeURIComponent(target)}`);
  await page.getByLabel("Email", { exact: true }).fill(`${who}@example.test`);
  await page.getByLabel("Password", { exact: true }).fill("synthetic-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.waitForURL((url) => !url.pathname.startsWith("/login"));
  await page.locator('body[data-app-ready="true"]').waitFor();
}
const clean = async (page: Page) =>
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
/** No ISO timestamp, enum value, control name, identifier or API text in what a person reads. */
const RAW =
  /\b[A-Z]+(_[A-Z]+)+\b|\b[a-z]+(_[a-z]+)+\b|\b[a-z]+\.[a-z_]+\b(?!\w*\.\w{2,4}\b)|[0-9a-f]{8}-[0-9a-f]{4}-|\d{4}-\d{2}-\d{2}T|must never show|organization-profile|business-facts|website-domain|runtime-controls/;
const noRaw = async (page: Page, scope = "main") => {
  const text = (await page.locator(scope).innerText())
    // An email address and a website host are real text a person recognizes.
    .replace(/[\w.+-]+@[\w.-]+/g, "")
    .replace(/\b[\w-]+(\.[\w-]+)*\.(example\.test|com)\b/g, "");
  expect(text).not.toMatch(RAW);
};
const onboarding = "/administration/onboarding/";
const users = "/administration/users/";
const platform = "/administration/platform/";
const setup = (page: Page, name: string) =>
  page.locator("[data-client]").filter({ hasText: name });
const person = (page: Page, name: string) =>
  page.locator("tbody tr").filter({ hasText: name });
/** The standing of a person, which is the status column, not a client's own chip. */
const standing = (page: Page, name: string) =>
  person(page, name).locator("td").nth(3).locator(".badge");
const component = (page: Page, key: string) =>
  page.locator(`[data-component="${key}"]`);
/** Answer one call of the console's own server with a typed API failure. */
const refuse = (page: Page, pattern: RegExp, code: string) =>
  page.route(pattern, (route) =>
    route.fulfill({
      status: 409,
      contentType: "application/json",
      body: JSON.stringify({ error: { code } }),
    }),
  );
test.beforeEach(async () => scenario("default"));
test.afterEach(async () => scenario("default"));

test.describe("Administration: Onboarding", () => {
  test("lists clients that are not live with progress and what blocks them", async ({
    page,
  }) => {
    await login(page, "admin", onboarding);
    await expect(
      page.getByRole("navigation", { name: "Administration" }),
    ).toContainText("Onboarding");
    // Live clients are not onboarding.
    await expect(page.locator("[data-client]")).toHaveCount(4);
    await expect(page.getByText("Synthetic Alpha")).toHaveCount(0);

    const ready = setup(page, "Juniper Living");
    await expect(ready.locator(".badge").first()).toHaveText("Onboarding");
    await expect(ready).toContainText("Ready to activate");
    await expect(ready.getByRole("progressbar")).toHaveAttribute(
      "aria-valuenow",
      "100",
    );
    await expect(ready).toContainText("100% complete");
    await expect(
      ready.getByRole("button", { name: "Activate client" }),
    ).toBeEnabled();

    const blocked = setup(page, "Harbor Grill");
    await expect(blocked.getByRole("progressbar")).toHaveAttribute(
      "aria-valuenow",
      "40",
    );
    await expect(blocked.getByRole("button")).toHaveCount(0);
    const items = blocked.getByRole("list").getByRole("listitem");
    // Two blockers name the same control: one row each, in the order reported.
    await expect(items).toHaveCount(3);
    await expect(items.nth(0)).toContainText("Add or finish a location");
    await expect(
      items.nth(0).getByRole("link", { name: "Open settings" }),
    ).toHaveAttribute("href", "/clients/harbor-grill/settings/");
    await expect(items.nth(1)).toContainText("Connect the missing accounts");
    await expect(
      items.nth(1).getByRole("link", { name: "Open integrations" }),
    ).toHaveAttribute("href", "/clients/harbor-grill/integrations/");
    // A control with no console screen says so rather than linking to a page that cannot fix it.
    await expect(items.nth(2)).toContainText("Create the business profile");
    await expect(items.nth(2)).toContainText("Not editable in the console yet");
    await expect(items.nth(2).getByRole("link")).toHaveCount(0);

    const prospect = setup(page, "Prospect Bakery");
    await expect(prospect.locator(".badge").first()).toHaveText("Prospect");
    await expect(prospect).toContainText("Not started");
    await expect(prospect.getByRole("progressbar")).toHaveCount(0);
    await expect(prospect.getByRole("button")).toHaveCount(0);

    await noRaw(page);
    await clean(page);
  });

  test("a client whose setup cannot be read says so and offers a retry, never 0%", async ({
    page,
  }) => {
    await login(page, "admin", onboarding);
    const broken = setup(page, "Unreadable Setup");
    await expect(broken).toContainText("Could not load");
    await expect(broken).toContainText("nothing is shown rather than a guess");
    await expect(broken.getByRole("link", { name: "Try again" })).toBeVisible();
    await expect(broken.getByRole("progressbar")).toHaveCount(0);
    await expect(broken).not.toContainText("%");
    await expect(broken.getByRole("button")).toHaveCount(0);
    // The others still show.
    await expect(setup(page, "Juniper Living")).toContainText("100% complete");
    await noRaw(page);
    await clean(page);
  });

  test("when every setup read fails nothing claims a percentage", async ({
    page,
  }) => {
    await scenario("onboarding_state_fails");
    await login(page, "admin", onboarding);
    await expect(page.getByText("Could not load")).toHaveCount(3);
    await expect(page.getByRole("progressbar")).toHaveCount(0);
    await expect(
      page.getByRole("button", { name: "Activate client" }),
    ).toHaveCount(0);
    await clean(page);
  });

  test("activating asks first and sends the version the readiness was judged on", async ({
    page,
  }) => {
    await login(page, "admin", onboarding);
    await setup(page, "Juniper Living")
      .getByRole("button", { name: "Activate client" })
      .click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toContainText("Activate Juniper Living?");
    await expect(dialog).toContainText("first website crawl starts");
    await noRaw(page, "dialog[open]");
    await dialog.getByRole("button", { name: "Cancel" }).click();
    expect(await requests()).toEqual([]);

    await setup(page, "Juniper Living")
      .getByRole("button", { name: "Activate client" })
      .click();
    await dialog.getByRole("button", { name: "Activate client" }).click();
    // It is live now, so it leaves the onboarding list.
    await expect(setup(page, "Juniper Living")).toHaveCount(0);
    expect(await requests()).toMatchObject([
      {
        path: "activate",
        organization_id: "00000051-0000-4000-8000-000000000000",
        body: { expected_version: 3 },
      },
    ]);
    await page.goto("/administration/");
    await expect(
      page
        .locator("tbody tr")
        .filter({ hasText: "Juniper Living" })
        .locator(".badge"),
    ).toHaveText("Active");
  });

  test("an activation the API refuses shows a designed message in the dialog", async ({
    page,
  }) => {
    await login(page, "admin", onboarding);
    await refuse(page, /\/activate\/$/, "ONBOARDING_INCOMPLETE");
    await setup(page, "Juniper Living")
      .getByRole("button", { name: "Activate client" })
      .click();
    const dialog = page.getByRole("dialog");
    await dialog.getByRole("button", { name: "Activate client" }).click();
    await expect(dialog).toContainText("Setup is not complete any more");
    await expect(dialog).not.toContainText("ONBOARDING");
    await expect(dialog.getByRole("button", { name: "Cancel" })).toBeEnabled();
    await noRaw(page, "dialog[open]");
    await clean(page);
  });

  test("no client onboarding is a designed empty state with a next step", async ({
    page,
  }) => {
    await scenario("onboarding_empty");
    await login(page, "admin", onboarding);
    await expect(page.getByText("No clients are onboarding")).toBeVisible();
    await expect(
      page.getByRole("link", { name: "Review clients" }),
    ).toHaveAttribute("href", "/administration/");
    await clean(page);
  });

  test("the client list failing is a designed error", async ({ page }) => {
    await scenario("error");
    await login(page, "admin", onboarding);
    await expect(
      page.getByText("Onboarding is temporarily unavailable"),
    ).toBeVisible();
    await expect(page.getByRole("link", { name: "Try again" })).toBeVisible();
    await expect(page.locator("[data-client]")).toHaveCount(0);
    await noRaw(page);
    await clean(page);
  });
});

test.describe("Administration: Users", () => {
  test("shows each person's role, clients and standing", async ({ page }) => {
    await login(page, "admin", users);
    await expect(person(page, "Mike Prickett")).toContainText(
      "Platform administrator",
    );
    await expect(person(page, "Mike Prickett")).toContainText("No clients");
    await expect(standing(page, "Mike Prickett")).toHaveText("Active");

    const dana = person(page, "Dana Rivera");
    await expect(dana).toContainText("dana@example.test");
    await expect(dana).toContainText("Owner, Manager");
    await expect(dana).toContainText("Synthetic Alpha");
    await expect(dana).toContainText("Synthetic Beta");
    await expect(standing(page, "Dana Rivera")).toHaveText("Active");

    const pat = person(page, "Pat Lee");
    await expect(pat).toContainText("Viewer");
    // The client's own chip and the person's standing both say invited.
    await expect(pat.locator("td").nth(2).locator(".badge")).toHaveText(
      "Invited",
    );
    await expect(standing(page, "Pat Lee")).toHaveText("Invited");
    await expect(
      pat.getByRole("button", { name: "Cancel invitation to Synthetic Alpha" }),
    ).toBeEnabled();

    await expect(standing(page, "Sam Ortiz")).toHaveText("Suspended");
    // No display name: the email stands in, once.
    const unnamed = person(page, "no-name@example.test");
    await expect(unnamed).toContainText("No role yet");
    await expect(standing(page, "no-name@example.test")).toHaveText(
      "No access",
    );
    await expect(standing(page, "Kim Park")).toHaveText("Deactivated");
    // Read-only: only the invitation can be acted on.
    const buttons = page.locator("main").getByRole("button");
    await expect(buttons).toHaveCount(1);
    await expect(buttons).toHaveText("Cancel invitation");
    await noRaw(page);
    await clean(page);
  });

  test("cancelling an invitation asks first, then removes it with its version", async ({
    page,
  }) => {
    await login(page, "admin", users);
    const cancel = () =>
      person(page, "Pat Lee")
        .getByRole("button", { name: /^Cancel invitation/ })
        .click();
    await cancel();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toContainText("Cancel Pat Lee's invitation?");
    await expect(dialog).toContainText(
      "no longer be able to join Synthetic Alpha",
    );
    await noRaw(page, "dialog[open]");
    await dialog.getByRole("button", { name: "Keep invitation" }).click();
    expect(await requests()).toEqual([]);

    await cancel();
    await dialog.getByRole("button", { name: "Cancel invitation" }).click();
    await expect(standing(page, "Pat Lee")).toHaveText("No access");
    await expect(person(page, "Pat Lee").getByRole("button")).toHaveCount(0);
    expect(await requests()).toMatchObject([
      {
        path: "cancel-invitation",
        invitation_id: "00000801-0000-4000-8000-000000000000",
        body: { expected_version: 1 },
      },
    ]);
  });

  test("an invitation that already changed shows a designed message", async ({
    page,
  }) => {
    await login(page, "admin", users);
    await refuse(page, /\/cancel\/$/, "INVITATION_CONFLICT");
    await person(page, "Pat Lee")
      .getByRole("button", { name: /^Cancel invitation/ })
      .click();
    const dialog = page.getByRole("dialog");
    await dialog.getByRole("button", { name: "Cancel invitation" }).click();
    await expect(dialog).toContainText("already answered or cancelled");
    await expect(dialog).not.toContainText("INVITATION");
    await clean(page);
  });

  test("people are paged and the pages link to each other", async ({
    page,
  }) => {
    await scenario("users_many");
    await login(page, "admin", users);
    await expect(page.locator("tbody tr")).toHaveCount(50);
    await expect(page.getByRole("link", { name: "Previous" })).toHaveCount(0);
    await page.getByRole("link", { name: "Next" }).click();
    await expect(page).toHaveURL(/offset=50/);
    await expect(page.locator("tbody tr")).toHaveCount(10);
    await expect(page.getByRole("link", { name: "Next" })).toHaveCount(0);
    await page.getByRole("link", { name: "Previous" }).click();
    await expect(page).not.toHaveURL(/offset/);
    await expect(page.locator("tbody tr")).toHaveCount(50);
    await clean(page);
  });

  test("a bad page number is refused, not guessed", async ({ page }) => {
    await login(page, "admin", users);
    const response = await page.goto(`${users}?offset=-4`);
    expect(response?.status()).toBe(400);
  });

  test("no people is a designed empty state", async ({ page }) => {
    await scenario("users_empty");
    await login(page, "admin", users);
    await expect(page.getByText("No people yet")).toBeVisible();
    await expect(page.locator("table")).toHaveCount(0);
    await clean(page);
  });

  test("the directory failing is a designed error, never an empty table", async ({
    page,
  }) => {
    await scenario("users_error");
    await login(page, "admin", users);
    await expect(
      page.getByText("People are temporarily unavailable"),
    ).toBeVisible();
    await expect(page.getByRole("link", { name: "Try again" })).toBeVisible();
    await expect(page.locator("table")).toHaveCount(0);
    await noRaw(page);
    await clean(page);
  });
});

test.describe("Administration: Platform / system", () => {
  test("summarizes each part in plain words and keeps the detail behind Details", async ({
    page,
  }) => {
    await scenario("system_default");
    await login(page, "admin", platform);
    await expect(
      page.getByRole("heading", { name: "Platform / system administration" }),
    ).toBeVisible();
    await expect(page.locator("[data-system] .panelhead .badge")).toHaveText(
      "Needs attention",
    );
    await expect(component(page, "database")).toContainText(
      "The database is reachable.",
    );
    await expect(component(page, "database").locator(".badge")).toHaveText(
      "Healthy",
    );
    await expect(component(page, "scheduler")).toContainText(
      "Scheduled work is being dispatched on time.",
    );
    await expect(component(page, "queue")).toContainText(
      "4 jobs gave up after failing.",
    );
    await expect(component(page, "queue").locator(".badge")).toHaveText(
      "Needs attention",
    );
    await expect(component(page, "runs")).toContainText(
      "3 workflow runs failed in the last 24 hours.",
    );
    await expect(component(page, "integrations")).toContainText(
      "2 connections need attention.",
    );
    await expect(
      component(page, "integrations").getByRole("link", {
        name: "Open integrations",
      }),
    ).toHaveAttribute("href", "/integrations/");
    // Reasons and times are not on the page itself.
    await expect(page.locator("[data-system]")).not.toContainText(
      "stopped responding",
    );
    await noRaw(page, "[data-system]");
    await clean(page);
  });

  test("dead letters open a Details dialog with the reasons and counts", async ({
    page,
  }) => {
    await login(page, "admin", platform);
    await component(page, "queue")
      .getByRole("button", { name: "Background work details" })
      .click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toContainText("System details");
    await expect(dialog).toContainText("Jobs that gave up");
    const reasons = dialog
      .locator(".listrow")
      .filter({ hasText: "Failed for good" });
    await expect(reasons).toContainText("2");
    await expect(dialog).toContainText("The worker stopped responding");
    await expect(dialog).toContainText("Ran out of retries");
    await expect(dialog).toContainText("Last scheduled dispatch");
    await expect(dialog).toContainText("Nothing due is waiting.");
    await noRaw(page, "dialog[open]");
    await clean(page);
    await dialog.getByRole("button", { name: "Close", exact: true }).click();
    await expect(dialog).toBeHidden();
  });

  test("everything healthy says so", async ({ page }) => {
    await scenario("system_healthy");
    await login(page, "admin", platform);
    await expect(page.locator("[data-system] .panelhead .badge")).toHaveText(
      "Healthy",
    );
    await expect(component(page, "queue")).toContainText(
      "Nothing has given up and nothing is waiting too long.",
    );
    await expect(component(page, "runs")).toContainText(
      "No workflow runs failed in the last 24 hours.",
    );
    await expect(
      page.getByRole("link", { name: "Open integrations" }),
    ).toHaveCount(0);
    await clean(page);
  });

  test("a part that could not be read is Unknown, never healthy and never zero", async ({
    page,
  }) => {
    await scenario("system_unknown");
    await login(page, "admin", platform);
    await expect(page.locator("[data-system] .panelhead .badge")).toHaveText(
      "Unknown",
    );
    for (const key of ["scheduler", "queue", "runs"])
      await expect(component(page, key).locator(".badge")).toHaveText(
        "Unknown",
      );
    await expect(component(page, "queue")).toContainText(
      "We could not check the work queue.",
    );
    await expect(component(page, "runs")).toContainText(
      "We could not check recent workflow runs.",
    );
    await expect(component(page, "queue")).not.toContainText("0");
    await expect(component(page, "runs")).not.toContainText("0");
    // There is nothing to show details of.
    await expect(component(page, "queue").getByRole("button")).toHaveCount(0);
    await noRaw(page, "[data-system]");
    await clean(page);
  });

  test("the status failing is a designed error", async ({ page }) => {
    await scenario("system_error");
    await login(page, "admin", platform);
    await expect(
      page.getByText("System status is temporarily unavailable"),
    ).toBeVisible();
    await expect(page.getByRole("link", { name: "Try again" })).toBeVisible();
    await expect(page.locator("[data-system]")).toHaveCount(0);
    await noRaw(page);
    await clean(page);
  });
});

test("a person who is not an administrator sees no access on every tab and nothing is called", async ({
  page,
}) => {
  await login(page, "a", "/");
  for (const path of [onboarding, users, platform]) {
    await page.goto(path);
    await expect(
      page.getByText("You do not have access to Administration"),
    ).toBeVisible();
    await expect(
      page.locator("table, [data-system], [data-onboarding]"),
    ).toHaveCount(0);
  }
  expect(await requests()).toEqual([]);
  await clean(page);
});
