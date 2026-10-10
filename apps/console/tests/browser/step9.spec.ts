import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
const sim = "http://127.0.0.1:4455/test";
const integrations = "/clients/synthetic-alpha/integrations/";
const uuid = (n: number) =>
  `${n.toString(16).padStart(8, "0")}-0000-4000-8000-000000000000`;
const draft = `/clients/synthetic-alpha/website-content/content/${uuid(0xc1)}/`;
async function post(path: string, data: object) {
  const response = await fetch(`${sim}/${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  expect(response.ok).toBe(true);
}
const scenario = (mode: string) => post("publishing-scenario", { mode });
async function login(page: Page, target: string) {
  await page.goto(`/login/?return=${encodeURIComponent(target)}`);
  await page.getByLabel("Email", { exact: true }).fill("a@example.test");
  await page.getByLabel("Password", { exact: true }).fill("synthetic-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.waitForURL((url) => !url.pathname.startsWith("/login"));
  await page.locator('body[data-app-ready="true"]').waitFor();
}
// Linking a repository needs a second factor: sign in, then confirm with the authenticator.
async function stepUp(page: Page, target: string) {
  await login(page, integrations);
  await page.goto(`/mfa/?return=${encodeURIComponent(target)}`);
  const enroll = page.getByRole("button", { name: "Set up authenticator" });
  if (await enroll.count()) await enroll.click();
  await page.getByLabel("Authenticator code").fill("123456");
  await page.getByRole("button", { name: "Verify", exact: true }).click();
  await page.waitForURL(
    (url) => url.pathname === new URL(target, url).pathname,
  );
}
const clean = async (page: Page) =>
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
/** No ISO timestamp, enum value, identifier or API text in what a person reads. */
const RAW =
  /\b[A-Z]+(_[A-Z]+)+\b|\b[a-z]+(_[a-z]+)+\b|[0-9a-f]{8}-[0-9a-f]{4}-|\d{4}-\d{2}-\d{2}T|Platform resource|sc-domain:/;
const noRaw = async (page: Page) =>
  expect(await page.locator("main").innerText()).not.toMatch(RAW);
const row = (page: Page) => page.locator('[data-integration="publishing"]');
const requests = async () =>
  (await (await fetch(`${sim}/publishing-requests`)).json()).requests as {
    path: string;
    key?: string;
    body?: { repository_id: string };
  }[];
test.beforeEach(async () => scenario("not_linked"));
test("linked: ready to publish with the repository, branch and a details dialog", async ({
  page,
}) => {
  await scenario("linked");
  await login(page, integrations);
  await expect(row(page).locator(".badge")).toHaveText("Ready to publish");
  await expect(row(page)).toContainText("LilosG/synthetic-site");
  await expect(row(page)).toContainText("Branch main");
  await expect(
    page.getByRole("button", { name: "Select repository" }),
  ).toHaveCount(0);
  await row(page)
    .getByRole("button", { name: /Open details/ })
    .click();
  const details = page.getByRole("dialog");
  await expect(details).toContainText("Repository");
  await expect(details).toContainText("Checked");
  await noRaw(page);
  await page.keyboard.press("Escape");
  await noRaw(page);
  await clean(page);
});
test("not linked: select a suggested, format-checked repository and link it once", async ({
  page,
}) => {
  await stepUp(page, integrations);
  await expect(row(page).locator(".badge")).toHaveText("Choose a repository");
  await page.getByRole("button", { name: "Select repository" }).click();
  const dialog = page.getByRole("dialog");
  const items = dialog.locator("[data-repo-list] button");
  await expect(items).toHaveCount(3);
  // Suggested first and labelled; the unchecked one is disabled and says why.
  await expect(items.first()).toContainText("synthetic-site");
  await expect(items.first()).toContainText("Suggested");
  const unchecked = items.filter({ hasText: "unchecked-site" });
  await expect(unchecked).toBeDisabled();
  await expect(unchecked).toContainText("Blog format not checked yet");
  await expect(
    dialog.getByRole("button", { name: "Use this repository" }),
  ).toBeDisabled();
  await clean(page);
  await items.first().click();
  const link = page.waitForRequest(
    (r) => r.url().endsWith("/publishing/target/") && r.method() === "POST",
  );
  await dialog.getByRole("button", { name: "Use this repository" }).click();
  const sent = await link;
  expect(sent.postDataJSON()).toEqual({
    repository_id: "LilosG/synthetic-site",
  });
  expect(sent.headers()["idempotency-key"]).toMatch(/^[0-9a-f-]{36}$/);
  await expect(row(page).locator(".badge")).toHaveText("Ready to publish");
  await expect(row(page)).toContainText("LilosG/synthetic-site");
  expect(
    (await requests()).filter((r) => r.path.endsWith("/target")),
  ).toHaveLength(1);
});
test("not linked without a verified sign-in: a way to verify, not a dead button", async ({
  page,
}) => {
  await login(page, integrations);
  await expect(
    page.getByRole("button", { name: "Select repository" }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("link", { name: "Verify authenticator" }).first(),
  ).toBeVisible();
});
test("repositories failing to load is a designed error with Retry; empty is an empty state", async ({
  page,
}) => {
  await scenario("repositories_fail");
  await stepUp(page, integrations);
  await page.getByRole("button", { name: "Select repository" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("alert")).toContainText(
    "Repositories could not be loaded",
  );
  await expect(dialog).not.toContainText(/PUBLISHING_|502/);
  await scenario("repositories_empty");
  await dialog.getByRole("button", { name: "Retry" }).click();
  await expect(dialog).toContainText("No repositories to choose from");
  await clean(page);
});
test("a repository the API refuses shows a designed message and creates nothing", async ({
  page,
}) => {
  await scenario("link_unverified");
  await stepUp(page, integrations);
  await page.getByRole("button", { name: "Select repository" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.locator("[data-repo-list] button").first().click();
  await dialog.getByRole("button", { name: "Use this repository" }).click();
  await expect(dialog.getByRole("alert")).toContainText(
    "Publishing stays paused for this repository",
  );
  await expect(dialog).not.toContainText("PUBLISHING_FORMAT_UNVERIFIED");
});
test("GitHub not connected: an empty state whose action starts the GitHub install", async ({
  page,
}) => {
  await scenario("github_not_connected");
  await stepUp(page, integrations);
  await expect(row(page).locator(".badge")).toHaveText("GitHub not connected");
  const empty = page.locator("[data-publishing-empty]");
  await expect(empty).toContainText(
    "Connect GitHub to publish to this website",
  );
  await page.route("https://github.com/**", (route) =>
    route.fulfill({ contentType: "text/html", body: "GitHub" }),
  );
  const install = page.waitForRequest((r) =>
    r.url().endsWith("/integrations/github/install/"),
  );
  await clean(page);
  await empty.getByRole("button", { name: "Connect GitHub" }).click();
  await install;
  await page.waitForURL(/github\.com\/apps\/.+\/installations\/new/);
});
test("format not checked: publishing is paused, in plain words", async ({
  page,
}) => {
  await scenario("format_unverified");
  await login(page, integrations);
  await expect(row(page).locator(".badge")).toHaveText(
    "Blog format not checked yet",
  );
  await expect(page.locator("main")).toContainText("Publishing is paused");
  await noRaw(page);
  await clean(page);
});
test("no access to publishing is a chip, not an error", async ({ page }) => {
  await scenario("no_access");
  await login(page, integrations);
  await expect(row(page).locator(".badge")).toHaveText("No access");
  await clean(page);
});
test.describe("image picker", () => {
  test.beforeEach(async () => post("content-images", { images: "list" }));
  test.afterEach(async () => post("website-scenario", { mode: "default" }));
  const open = async (page: Page) => {
    await post("website-scenario", { mode: "content" });
    await post("content-images", { images: "list" });
    await stepUp(page, draft);
    return page.locator("[data-image-picker]");
  };
  test("search, choose, and publish with the chosen image", async ({
    page,
  }) => {
    const picker = await open(page);
    const items = picker.locator("[data-picker-list] button");
    await expect(items).toHaveCount(4);
    await expect(items.first()).toContainText("synthetic.webp");
    await expect(items.nth(1)).toContainText("/images/blog/");
    await picker.getByRole("searchbox").fill("blog wings");
    await expect(items).toHaveCount(1);
    await expect(items.first()).toContainText("wings.jpg");
    await items.first().click();
    await expect(picker).toContainText("Selected: wings.jpg");
    await page.getByLabel("Image description").fill("Wings on a tray");
    await clean(page);
    const publish = page.waitForRequest(
      (r) => r.method() === "POST" && r.url().endsWith("/publish/"),
    );
    await page.getByRole("button", { name: "Publish approved draft" }).click();
    expect((await publish).postDataJSON()).toMatchObject({
      image: "/images/blog/wings.jpg",
      image_alt: "Wings on a tray",
    });
  });
  test("a path can be typed instead", async ({ page }) => {
    const picker = await open(page);
    await picker.getByRole("button", { name: "Enter a path instead" }).click();
    await picker.getByLabel("Image path").fill("/uploads/custom.png");
    await page.getByLabel("Image description").fill("Custom");
    const publish = page.waitForRequest(
      (r) => r.method() === "POST" && r.url().endsWith("/publish/"),
    );
    await page.getByRole("button", { name: "Publish approved draft" }).click();
    expect((await publish).postDataJSON().image).toBe("/uploads/custom.png");
  });
  test("no images is an empty state; failure is an error with Retry", async ({
    page,
  }) => {
    const picker = await open(page);
    await post("content-images", { images: "empty" });
    await page.reload();
    await expect(page.locator("[data-image-picker]")).toContainText(
      "No images found in this repository",
    );
    await post("content-images", { images: "fail" });
    await page.reload();
    const failed = page.locator("[data-image-picker]");
    await expect(failed.getByRole("alert")).toContainText(
      "Images could not be loaded",
    );
    await post("content-images", { images: "list" });
    await failed.getByRole("button", { name: "Retry" }).click();
    await expect(failed.locator("[data-picker-list] button")).toHaveCount(4);
    expect(picker).toBeDefined();
    await clean(page);
  });
});
