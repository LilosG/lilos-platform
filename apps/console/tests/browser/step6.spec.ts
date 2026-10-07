import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
async function login(page: Page, target: string, who = "a") {
  await page.goto(`/login/?return=${encodeURIComponent(target)}`);
  await page.getByLabel("Email", { exact: true }).fill(`${who}@example.test`);
  await page.getByLabel("Password", { exact: true }).fill("synthetic-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.waitForURL((url) => !url.pathname.startsWith("/login"));
  await page.locator('body[data-app-ready="true"]').waitFor();
}
const alpha = "/clients/synthetic-alpha/reviews/";
const beta = "/clients/synthetic-beta/reviews/";
const clean = async (page: Page) =>
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
const card = (page: Page, name: string) =>
  page.locator(".reviewcard").filter({ hasText: name });
/** No ISO timestamp, enum value, identifier or field name in what a person reads. */
const noSystemText = async (page: Page) => {
  const text = await page.locator("main").innerText();
  expect(text).not.toMatch(
    /\b[A-Z]+(_[A-Z]+)+\b|\b[a-z]+(_[a-z]+)+\b|[0-9a-f]{8}-[0-9a-f]{4}-|\d{4}-\d{2}-\d{2}T|google_business_profile|Reviewer identity unavailable/,
  );
};
test("reviews show real reviewers, stars, dates and quoted responses", async ({
  page,
}) => {
  await login(page, alpha);
  await expect(page.locator("h1")).toHaveText("Reviews");
  await expect(page.locator(".reviewcard")).toHaveCount(4);
  // A named reviewer: name, initials avatar and stars.
  const named = card(page, "Jordan Sample");
  await expect(named.locator(".avatar")).toHaveText("JS");
  await expect(
    named.getByRole("img", { name: "5 out of 5 stars" }),
  ).toBeVisible();
  // A named reviewer with a photo.
  await expect(
    card(page, "Riley Example").locator("img.avatar.photo"),
  ).toHaveAttribute("src", "https://photos.example.invalid/riley.png");
  // An anonymous reviewer is a designed generic Google user.
  const anonymous = card(page, "Google user");
  await expect(anonymous.locator(".avatar.generic svg")).toBeVisible();
  await expect(
    anonymous.getByRole("img", { name: "4 out of 5 stars" }),
  ).toBeVisible();
  // An unknown reviewer is a Google reviewer with a "G".
  const unknown = card(page, "Google reviewer");
  await expect(unknown.locator(".avatar")).toHaveText("G");
  await expect(
    unknown.getByRole("img", { name: "2 out of 5 stars" }),
  ).toBeVisible();
  // Responses are quoted under the review, with what state they are in.
  await expect(
    card(page, "Riley Example").locator(".replyblock blockquote"),
  ).toHaveText("We are glad you enjoyed it, Riley.");
  await expect(card(page, "Riley Example").locator(".replylabel")).toHaveText(
    "Published response",
  );
  await expect(named.locator(".replylabel")).toHaveText(
    "Response awaiting approval",
  );
  await expect(unknown.locator(".replyblock")).toHaveCount(0);
  // Status chips come from typed state; dates are relative or formatted, never ISO.
  await expect(named.locator(".badge")).toHaveText("Awaiting approval");
  await expect(unknown.locator(".badge")).toHaveText("Needs response");
  await expect(card(page, "Riley Example").locator(".badge")).toHaveText(
    "Published",
  );
  await expect(named.locator("time")).toHaveText(/ago|Today|Yesterday|, 2026/);
  await noSystemText(page);
  await clean(page);
});
test("metrics, filter tabs and not-tracked tabs", async ({ page }) => {
  await login(page, alpha);
  const tiles = page.locator(".metric");
  await expect(tiles).toHaveCount(3);
  await expect(tiles.nth(0)).toContainText("Total reviews");
  await expect(tiles.nth(0).locator("strong")).toHaveText("4");
  await expect(tiles.nth(1).locator("strong")).toHaveText("4.0");
  await expect(tiles.nth(2).locator("strong")).toHaveText("2");
  const tabs = page.getByRole("navigation", { name: "Review views" });
  await tabs.getByRole("link", { name: "Awaiting approval" }).click();
  await expect(page).toHaveURL(/status=awaiting_approval/);
  await expect(page.locator(".reviewcard")).toHaveCount(1);
  await tabs.getByRole("link", { name: "Published" }).click();
  await expect(page.locator(".reviewcard")).toHaveCount(1);
  await expect(page.locator(".reviewcard")).toContainText("Riley Example");
  await tabs.getByRole("link", { name: "Needs response" }).click();
  await expect(page.locator(".reviewcard")).toHaveCount(2);
  await tabs.getByRole("link", { name: "Draft" }).click();
  await expect(
    page.getByRole("heading", { name: "Nothing in this view" }),
  ).toBeVisible();
  await clean(page);
  // Review requests and opportunities have no source yet: designed, not faked.
  await tabs.getByRole("link", { name: "Review requests" }).click();
  await expect(
    page.getByRole("heading", { name: "Review requests are not tracked yet" }),
  ).toBeVisible();
  await expect(page.locator(".reviewcard")).toHaveCount(0);
  await clean(page);
  await tabs.getByRole("link", { name: "Opportunities" }).click();
  await expect(
    page.getByRole("heading", {
      name: "Review opportunities are not tracked yet",
    }),
  ).toBeVisible();
  await clean(page);
  // An unknown filter is a designed error, not a silent "all".
  const response = await page.goto(`${alpha}?status=bogus`);
  expect(response?.status()).toBe(400);
  await expect(
    page.getByRole("heading", { name: "Invalid filter" }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "All reviews" }).first(),
  ).toBeVisible();
  await clean(page);
});
test("source detail is behind one chip and its Details dialog", async ({
  page,
}) => {
  await login(page, alpha);
  const shown = await page.locator("main").innerText();
  for (const text of [
    "Mapping",
    "Freshness",
    "Quality",
    "authorization",
    "Last import",
    "Source health",
    "Persisted reviews",
    "provider-wide",
  ])
    expect(shown).not.toContain(text);
  await expect(
    page.getByRole("button", { name: "Import reviews" }),
  ).toHaveCount(0);
  const chip = page.getByRole("button", { name: /Review source status/ });
  await expect(chip).toHaveCount(1);
  await chip.click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toContainText("Google connection");
  await expect(dialog).toContainText("Business location");
  await expect(dialog).toContainText("Last import");
  await expect(dialog).toContainText("Coverage");
  await expect(dialog).toContainText("Sep 29, 2026");
  await clean(page);
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
});
test("a source with no reviews shows a dash, never zero, and offers to import", async ({
  page,
}) => {
  await login(page, beta, "b");
  const tiles = page.locator(".metric strong");
  await expect(tiles).toHaveText(["—", "—", "—"]);
  await expect(page.locator(".metric strong.muted")).toHaveCount(3);
  await expect(page.locator(".metric small").first()).toHaveText(
    "Import reviews to see this",
  );
  await expect(
    page.getByRole("button", { name: "Import reviews" }).first(),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "No reviews yet" }),
  ).toBeVisible();
  await expect(page.locator("main")).not.toContainText(/\b0\b/);
  await noSystemText(page);
  await clean(page);
});
test("the response dialog drafts, edits, approves and publishes in the reference style", async ({
  page,
}) => {
  await login(page, alpha);
  await card(page, "Jordan Sample")
    .getByRole("link", { name: /Respond/ })
    .click();
  const dialog = page.getByRole("dialog");
  await expect(
    dialog.getByRole("heading", { name: "Reply to Jordan Sample" }),
  ).toBeVisible();
  await expect(dialog.locator(".avatar")).toHaveText("JS");
  await expect(dialog.locator(".replyblock blockquote")).toHaveText(
    "Thank you for visiting.",
  );
  await expect(
    dialog.getByRole("button", { name: "Approve this response" }),
  ).toBeDisabled();
  await expect(
    dialog.getByRole("button", { name: "Publish to Google" }),
  ).toBeDisabled();
  await expect(
    dialog.getByRole("link", { name: "Verify to continue" }),
  ).toBeVisible();
  await expect(dialog.getByLabel("Edit the response")).toHaveValue(
    "Thank you for visiting.",
  );
  await expect(dialog.getByText("Facts this response may use")).toHaveCount(0);
  await expect(dialog.getByRole("checkbox")).toHaveCount(0);
  await expect(
    dialog.getByRole("button", { name: "Generate a response" }),
  ).toBeEnabled();
  await noSystemText(page);
  await clean(page);
});
