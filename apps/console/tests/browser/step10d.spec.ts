import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
async function login(page: Page, target: string) {
  await page.goto(`/login/?return=${encodeURIComponent(target)}`);
  await page.getByLabel("Email", { exact: true }).fill("b@example.test");
  await page.getByLabel("Password", { exact: true }).fill("synthetic-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.waitForURL((url) => !url.pathname.startsWith("/login"));
  await page.locator('body[data-app-ready="true"]').waitFor();
  if (target.includes("google-business-profile"))
    await page.locator("[data-gbp][data-ready]").waitFor();
}
const search = "/clients/synthetic-beta/local-search/";
const gbp = `${search}google-business-profile/`;
const header = (page: Page) => page.locator(".pagehead").first();
test.beforeEach(async ({ request }) => {
  await request.post("http://127.0.0.1:4455/test/gbp-reset", { data: {} });
});
test("Google Business Profile is a labelled tab with its own sections", async ({
  page,
}) => {
  await login(page, search);
  const tabs = page.getByRole("navigation", { name: "Local Search sections" });
  await expect(
    tabs.getByRole("link", { name: "Google Business Profile" }),
  ).toBeVisible();
  await login(page, gbp);
  const sections = page.getByRole("navigation", {
    name: "Business Profile sections",
  });
  for (const name of ["Posts", "Photos", "Special hours", "Profile"])
    await expect(sections.getByRole("link", { name })).toBeVisible();
});
test("the header's New post opens the post dialog from the Business Profile view", async ({
  page,
}) => {
  await login(page, gbp);
  await header(page).getByRole("button", { name: "New post" }).click();
  await expect(page.getByRole("dialog")).toContainText("Write a Google post");
  await page.getByLabel("Post copy").fill("Patio open late tonight");
  const saved = page.waitForRequest((r) => r.url().endsWith("/posts/"));
  await page.getByRole("button", { name: "Save for approval" }).click();
  expect((await saved).postDataJSON().content).toBe("Patio open late tonight");
});
test("on the default view New post leads straight to the dialog", async ({
  page,
}) => {
  await login(page, search);
  await header(page).getByRole("link", { name: "New post" }).click();
  await expect(page).toHaveURL(/view=posts/);
  await expect(page.getByRole("dialog")).toContainText("Write a Google post");
  await expect(page).not.toHaveURL(/compose=/);
});
test("a profile with writes off shows a disabled button, the reason and the next step", async ({
  page,
}) => {
  await login(page, gbp);
  await page
    .getByLabel("Business Profile location")
    .selectOption({ label: "Cococabana Kitchen" });
  await expect(page).toHaveURL(/location=/);
  const button = header(page).getByRole("button", { name: "New post" });
  await expect(button).toBeDisabled();
  await expect(header(page)).toContainText("Posting is turned off");
  await expect(
    header(page).getByRole("link", { name: /Integrations/ }),
  ).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
});
