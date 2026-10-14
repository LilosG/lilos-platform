import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import fixtures from "../fixtures/phase3.json" with { type: "json" };
const sim = "http://127.0.0.1:4455/test";
const gbp = "/clients/synthetic-beta/local-search/google-business-profile/";
const reviews = "/clients/synthetic-alpha/reviews/";
const location = fixtures.workspace.location_id;
const removedFirst = "33333333-3333-4333-8333-3333333333a1";
const removedSecond = "33333333-3333-4333-8333-3333333333a2";
async function login(page: Page, who: string, target: string) {
  await page.goto(`/login/?return=${encodeURIComponent(target)}`);
  await page.getByLabel("Email", { exact: true }).fill(`${who}@example.test`);
  await page.getByLabel("Password", { exact: true }).fill("synthetic-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.waitForURL((url) => !url.pathname.startsWith("/login"));
  await page.locator('body[data-app-ready="true"]').waitFor();
  if (target.includes("google-business-profile"))
    await page.locator("[data-gbp][data-ready]").waitFor();
}
const clean = async (page: Page) =>
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
/** No enum value, typed code, id or timestamp reaches a person. */
const RAW =
  /\b[A-Z]+(_[A-Z]+)+\b|\b[a-z]+(_[a-z0-9]+)+\b|[0-9a-f]{8}-[0-9a-f]{4}-|\d{4}-\d{2}-\d{2}T/;
const noRaw = async (page: Page) =>
  expect(await page.locator("main").innerText()).not.toMatch(RAW);
test.beforeEach(async ({ request }) => {
  await request.post(`${sim}/gbp-reset`, { data: {} });
});

test.describe("Google posts Google has accepted but not confirmed", () => {
  test("a post waiting on Google is in progress; a parked one says what to do", async ({
    page,
    request,
  }) => {
    await request.post(`${sim}/gbp-waiting-posts`, { data: {} });
    await login(page, "b", `${gbp}?view=posts`);
    const post = (text: string) =>
      page.locator("[data-post-row]").filter({ hasText: text });
    const waiting = post("Trivia night");
    await expect(waiting).toContainText("Confirming with Google");
    await expect(waiting).toContainText("looks again automatically");
    await expect(waiting).not.toContainText("Needs attention");
    // Waiting on Google needs no action from a person.
    await expect(
      waiting.getByRole("button", { name: "Retry publishing" }),
    ).toHaveCount(0);

    const timedOut = post("Father's Day brunch");
    await expect(timedOut).toContainText("Needs attention");
    await expect(timedOut).toContainText("has not shown this post after a day");
    await expect(
      timedOut.getByRole("button", { name: "Retry publishing" }),
    ).toBeVisible();

    const reconnect = post("Happy hour moves indoors");
    await expect(reconnect).toContainText("Needs attention");
    await expect(reconnect).toContainText("Reconnect it in Integrations");
    await noRaw(page);
    await clean(page);
  });
});

test.describe("Reviews Google no longer lists", () => {
  test("the default inbox hides them and a chip with its count opens them", async ({
    page,
  }) => {
    await login(page, "a", reviews);
    const inbox = page.locator("[data-review-inbox]");
    await expect(inbox.locator("[data-review-id]")).toHaveCount(4);
    await expect(inbox).not.toContainText("Morgan Example");
    const chip = page.getByRole("link", { name: /No longer on Google/ });
    await expect(chip).toContainText("2");
    await chip.click();
    await expect(inbox.locator("[data-review-id]")).toHaveCount(2);
    await expect(inbox).toContainText("Morgan Example");
    await expect(
      inbox.locator("[data-review-id]").first().locator(".badge"),
    ).toHaveText("No longer on Google");
    await expect(inbox.getByRole("link", { name: /^Respond/ })).toHaveCount(0);
    await noRaw(page);
    await clean(page);
  });

  test("opening one is read-only, keeps its earlier reply, and offers no action", async ({
    page,
  }) => {
    await login(page, "a", `${reviews}locations/${location}/${removedFirst}/`);
    await expect(
      page.getByRole("heading", { name: "Review from Morgan Example" }),
    ).toBeVisible();
    const detail = page.locator("#review-detail");
    await expect(detail).toContainText("No longer on Google");
    await expect(detail).toContainText(
      "Google no longer lists this review, so it can’t be replied to. It may come back after the next import.",
    );
    // The earlier reply stays as history.
    await expect(detail).toContainText(
      "Thank you so much, and happy anniversary!",
    );
    for (const name of [
      /Approve this response/,
      /Publish to Google/,
      /Generate a response/,
      /Save draft|Save changes/,
    ])
      await expect(page.getByRole("button", { name })).toHaveCount(0);
    await expect(page.locator("textarea")).toHaveCount(0);
    await noRaw(page);
    await clean(page);
  });

  test("one with no earlier reply is read-only too", async ({ page }) => {
    await login(page, "a", `${reviews}locations/${location}/${removedSecond}/`);
    await expect(page.locator("#review-detail")).toContainText(
      "Google no longer lists this review",
    );
    await expect(page.locator("textarea")).toHaveCount(0);
    await expect(
      page.getByRole("button", { name: /Approve|Publish/ }),
    ).toHaveCount(0);
  });

  test("a client with none shows an empty state, and no chip until one exists", async ({
    page,
  }) => {
    await login(page, "b", "/clients/synthetic-beta/reviews/");
    await expect(
      page.getByRole("link", { name: /No longer on Google/ }),
    ).toHaveCount(0);
    await page.goto("/clients/synthetic-beta/reviews/?status=removed");
    await expect(
      page.getByRole("heading", { name: "Nothing has been dropped by Google" }),
    ).toBeVisible();
    await clean(page);
  });
});
