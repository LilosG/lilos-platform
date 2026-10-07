import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
const base = "/clients/synthetic-alpha/website-content/";
const sim = "http://127.0.0.1:4455/test";
const uuid = (n: number) =>
  `${n.toString(16).padStart(8, "0")}-0000-4000-8000-000000000000`;
const READY = uuid(0xc1);
const WRITING = uuid(0xc2);
const PAGE_ITEM = uuid(0xc4);
async function login(page: Page, target: string, who = "a") {
  await page.goto(`/login/?return=${encodeURIComponent(target)}`);
  await page.getByLabel("Email", { exact: true }).fill(`${who}@example.test`);
  await page.getByLabel("Password", { exact: true }).fill("synthetic-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.waitForURL((url) => !url.pathname.startsWith("/login"));
  await page.locator('body[data-app-ready="true"]').waitFor();
}
// Approving needs a second factor: sign in, then confirm with the authenticator.
async function stepUp(page: Page, target: string) {
  await login(page, base);
  await page.goto(`/mfa/?return=${encodeURIComponent(target)}`);
  const enroll = page.getByRole("button", { name: "Set up authenticator" });
  if (await enroll.count()) await enroll.click();
  await page.getByLabel("Authenticator code").fill("123456");
  await page.getByRole("button", { name: "Verify", exact: true }).click();
  await page.waitForURL(
    (url) => url.pathname === new URL(target, url).pathname,
  );
}
const scenario = async (
  request: import("@playwright/test").APIRequestContext,
  mode: string,
) => request.post(`${sim}/website-scenario`, { data: { mode } });
const requests = async (
  request: import("@playwright/test").APIRequestContext,
) =>
  (await (await request.get(`${sim}/content-requests`)).json()).requests as {
    kind: string;
    body: Record<string, unknown>;
  }[];
const clean = async (page: Page) =>
  expect(
    (await new AxeBuilder({ page }).analyze()).violations.map((v) => ({
      id: v.id,
      nodes: v.nodes.map((n) => n.target),
    })),
  ).toEqual([]);
// No enum value, typed code, id, timestamp or field name reaches a person.
const RAW =
  /\b[A-Z]+(_[A-Z]+)+\b|\b[a-z]+(_[a-z0-9]+)+\b|[0-9a-f]{8}-[0-9a-f]{4}-|\d{4}-\d{2}-\d{2}T|awaiting_|validation_|\bcompose|article_|CONTENT_/;
async function noRawText(page: Page) {
  const text = await page.locator("main").innerText();
  expect(text).not.toMatch(RAW);
  await expect(
    page.getByText(/\bundefined\b|\[object Object\]|\bNaN\b/),
  ).toHaveCount(0);
}
// The table must fit at desktop; on a phone the page itself never scrolls sideways.
async function noPageOverflow(page: Page) {
  const wide = await page.evaluate(
    () => document.documentElement.scrollWidth > window.innerWidth + 1,
  );
  if (wide) {
    const offenders = await page.evaluate(() =>
      [...document.querySelectorAll("body *")]
        .filter(
          (el) =>
            el.getBoundingClientRect().right > window.innerWidth + 1 &&
            !el.closest(".tablewrap, nav"),
        )
        .slice(0, 6)
        .map(
          (el) =>
            el.tagName +
            "." +
            el.className +
            " " +
            (el.textContent ?? "").slice(0, 30) +
            " in " +
            (el.parentElement?.tagName ?? ""),
        ),
    );
    expect(offenders).toEqual([]);
  }
}
test.beforeEach(async ({ request }) => {
  await scenario(request, "content");
});
test.afterEach(async ({ request }) => {
  await scenario(request, "default");
});

test("the list shows stage, words, revision and publication state as chips", async ({
  page,
}, info) => {
  await login(page, base + "content/");
  await expect(
    page.getByRole("heading", { name: /Articles and guides/ }),
  ).toBeVisible();
  const rows = page.locator("[data-content-list] [data-content-row]");
  await expect(rows).toHaveCount(4);
  const ready = rows.filter({ hasText: "Green Bay Packers Bar" });
  await expect(ready).toContainText("Blog post");
  await expect(ready.locator(".badge")).toHaveText([
    "Ready for review",
    "Awaiting review",
  ]);
  await expect(ready.locator("td.num")).toHaveText("1,520");
  const published = rows.filter({ hasText: "Wing night" });
  await expect(published.locator(".badge")).toHaveText([
    "Published",
    "Approved",
    "Live",
  ]);
  // A draft that does not exist yet has no length: a dash, never 0.
  const writing = rows.filter({ hasText: "Best places to watch" });
  await expect(writing.locator(".badge")).toHaveText(["Writing"]);
  await expect(writing.locator("td.num")).toHaveText("–");
  await expect(writing).toContainText("Writing…");
  await expect(
    page.getByRole("heading", { name: /Landing and service pages/ }),
  ).toBeVisible();
  await expect(
    page.locator("[data-landing-pages] [data-content-row]"),
  ).toHaveCount(1);
  await noRawText(page);
  await noPageOverflow(page);
  if (info.project.name === "desktop") {
    const clipped = await page
      .locator(".contenttable")
      .first()
      .evaluate((el) => el.scrollWidth > el.clientWidth + 1);
    expect(clipped).toBe(false);
  }
  await clean(page);
});

test("a failed item is a designed error with its typed reason and a retry", async ({
  page,
}) => {
  await login(page, base + "content/");
  const failure = page.locator("[data-content-failure]");
  await expect(failure).toHaveCount(1);
  await expect(failure.getByRole("alert")).toContainText(
    "The draft was not long or well linked enough",
  );
  await expect(failure).not.toContainText(/CONTENT_|FLOOR/);
  await failure.getByRole("button", { name: "Try again" }).click();
  await expect(page.getByLabel("What should it be about?")).toHaveValue(
    "write a guide to game day parking near Miss B's",
  );
  await clean(page);
});

test("the composer sends one prompt, a website and an optional type, then shows Writing", async ({
  page,
  request,
}) => {
  await login(page, base + "content/");
  await page.getByRole("button", { name: "New content" }).click();
  const dialog = page.getByRole("dialog", { name: "New content" });
  await expect(dialog).toBeVisible();
  const prompt = dialog.getByLabel("What should it be about?");
  await expect(prompt).toHaveAttribute(
    "placeholder",
    /Write a blog about why .+ is the best place to watch the game/,
  );
  const submit = dialog.getByRole("button", { name: "Write it" });
  await expect(submit).toBeDisabled();
  await expect(
    dialog.getByRole("radio", { name: "Let Claude decide" }),
  ).toBeChecked();
  for (const label of [
    "Blog post",
    "Listicle",
    "Landing page",
    "Service page",
    "Location page",
    "Guide",
  ])
    await expect(dialog.getByRole("radio", { name: label })).toBeVisible();
  await dialog.getByRole("radio", { name: "Listicle" }).check();
  await prompt.fill(
    "listicle: best places to watch Packers games in San Diego",
  );
  await expect(submit).toBeEnabled();
  await clean(page);
  await Promise.all([page.waitForEvent("load"), submit.click()]);
  const sent = (await requests(request)).find((r) => r.kind === "compose")!;
  expect(sent.body).toMatchObject({
    prompt: "listicle: best places to watch Packers games in San Diego",
    content_type: "listicle",
  });
  expect(sent.body.website_id).toMatch(/^[0-9a-f-]{36}$/);
  expect(sent.body.idempotency_key).toMatch(/^[0-9a-f-]{36}$/);
  const first = page.locator("[data-content-row]").first();
  await expect(first).toContainText("listicle: best places to watch");
  await expect(first.locator(".badge")).toHaveText("Writing");
});

test("a Writing item becomes ready on its own, without a manual refresh", async ({
  page,
  request,
}) => {
  test.setTimeout(45_000);
  await login(page, base + "content/");
  const row = page
    .locator("[data-content-row]")
    .filter({ hasText: "Best places to watch" });
  await expect(row.locator(".badge")).toHaveText("Writing");
  await request.post(`${sim}/content-advance`, { data: {} });
  await expect(row.locator(".badge").first()).toHaveText("Ready for review", {
    timeout: 20_000,
  });
  await expect(row.locator("td.num")).toHaveText("1,640");
});

test("the composer is unavailable with a stated reason when there is nothing to write for", async ({
  page,
  request,
}) => {
  await scenario(request, "no_website");
  await login(page, base + "content/");
  await expect(
    page.getByRole("heading", { name: "No website to write for" }),
  ).toBeVisible();
  const button = page.getByRole("button", { name: "New content" });
  await expect(button).toBeDisabled();
  await expect(button).toHaveAttribute(
    "title",
    "Add a website in Integrations first",
  );
  await expect(
    page.getByRole("link", { name: "Open Integrations" }),
  ).toBeVisible();
  await clean(page);
});

test("an empty Content tab is a designed state with a next action", async ({
  page,
  request,
}) => {
  await scenario(request, "content_empty");
  await login(page, base + "content/");
  await expect(
    page.getByRole("heading", { name: "No articles yet" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "No landing pages yet" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Write the first article" }).click();
  await expect(page.getByRole("dialog", { name: "New content" })).toBeVisible();
  await page.keyboard.press("Escape");
  await noRawText(page);
  await clean(page);
});

test("draft review shows the article, its measurements and every link", async ({
  page,
}) => {
  await login(page, `${base}content/${READY}/`);
  await expect(
    page.getByRole("heading", {
      name: "Miss B's: The Green Bay Packers Bar in San Diego",
      level: 1,
    }),
  ).toBeVisible();
  await expect(page.locator("[data-source-prompt]")).toContainText(
    "write a blog about Miss B's being the Green Bay Packers bar in San Diego",
  );
  // Word count against the floor.
  await expect(
    page.locator("[data-draft-summary] .detailmetrics"),
  ).toContainText("Minimum 1,400 · meets it");
  // Rendered preview, with a real link.
  await expect(page.locator(".draftpreview h2").first()).toHaveText(
    "Why Packers fans pick Miss B's in San Diego",
  );
  await expect(
    page.locator("[data-draft-preview] a", {
      hasText: "our full food and drink menu",
    }),
  ).toHaveAttribute("href", "/menu/");
  // Outline, SEO title and meta, FAQ.
  await expect(page.locator("[data-outline] li")).toHaveCount(5);
  await expect(page.locator("[data-seo-title]")).toHaveText(
    "Packers Bar in San Diego | Miss B's",
  );
  await expect(page.locator("[data-meta-description]")).toContainText(
    "Where to watch Green Bay Packers games",
  );
  await expect(page.locator("[data-faq]")).toHaveCount(2);
  // Quality checks as chips from typed codes.
  await expect(page.locator("[data-quality-checks] .badge").first()).toHaveText(
    "Meets length",
  );
  await expect(page.locator("[data-quality-checks] .badge.error")).toHaveCount(
    0,
  );
  // Outbound links, each verified.
  const links = page.locator("[data-outbound-link]");
  await expect(links).toHaveCount(4);
  await expect(links.locator(".badge")).toHaveText([
    "Verified",
    "Verified",
    "Verified",
    "Verified",
  ]);
  // Inbound edits as before and after, plus a typed reason where none could be made.
  const inbound = page.locator("[data-inbound-edit]");
  await expect(inbound).toHaveCount(2);
  await expect(inbound.first()).toContainText("/events/");
  await expect(inbound.first().locator(".beforeafter")).toContainText(
    "Visit the Green Bay Packers bar for game day.",
  );
  await expect(inbound.first().locator(".beforeafter")).toContainText(
    "[Green Bay Packers bar](/blog/green-bay-packers-bar-san-diego)",
  );
  await expect(inbound.nth(1)).toContainText(
    "This page has no editable link area",
  );
  await expect(page.locator("[data-revision]")).toHaveCount(1);
  await noRawText(page);
  await noPageOverflow(page);
  await clean(page);
});

test("a claim nothing backs blocks approval until it is confirmed; approval shows the exact change", async ({
  page,
  request,
}) => {
  await stepUp(page, `${base}content/${READY}/`);
  const claims = page.locator("[data-claims]");
  await expect(claims).toContainText("Miss B's opened in 1987");
  await expect(
    claims.locator("[data-claim='needs_confirmation'] .badge"),
  ).toHaveText("Needs confirmation");
  // Approve opens, but cannot be confirmed while a claim is open.
  await page.getByRole("button", { name: "Approve…" }).click();
  const dialog = page.locator("#content-approval");
  await expect(dialog).toContainText(
    "One claim still needs to be confirmed or removed.",
  );
  await expect(
    dialog.getByRole("button", { name: "Approve draft" }),
  ).toBeDisabled();
  await dialog.getByRole("button", { name: "Not yet" }).click();
  await expect(
    page.getByRole("heading", { name: "Draft review" }),
  ).toBeVisible();
  // Confirm the claim.
  await claims.getByRole("button", { name: "Confirm" }).click();
  await expect(claims.locator("[data-claim='confirmed'] .badge")).toHaveText(
    "Confirmed",
  );
  expect((await requests(request)).some((r) => r.kind === "confirm")).toBe(
    true,
  );
  // Approval shows exactly what will be added to the site.
  await page.getByRole("button", { name: "Approve…" }).click();
  const exact = dialog.locator("[data-exact-change]");
  await expect(exact).toContainText("synthetic/missbs-site");
  await expect(exact).toContainText("main");
  await expect(exact).toContainText(
    "src/content/blog/green-bay-packers-bar-san-diego.mdx",
  );
  await expect(exact).toContainText("A new file is added");
  await clean(page);
  await dialog.getByRole("button", { name: "Approve draft" }).click();
  await expect(page.locator("[data-draft-summary] .badge").first()).toHaveText(
    "Awaiting final approval",
  );
  const decision = (await requests(request)).find(
    (r) => r.kind === "decision",
  )!;
  expect(decision.body).toEqual({ stage: "editorial", approve: true });
});

test("regenerate sends the reviewer's instruction and waits for the new revision", async ({
  page,
  request,
}) => {
  test.setTimeout(45_000);
  await login(page, `${base}content/${READY}/`);
  await page.getByRole("button", { name: "Regenerate…" }).click();
  await page
    .getByLabel("What should change?")
    .fill("make it longer, add a section on game-day specials");
  await page.getByRole("button", { name: "Regenerate", exact: true }).click();
  await expect(page.locator("[data-content-status]")).toContainText(
    "Claude is writing a new revision",
  );
  const sent = (await requests(request)).find((r) => r.kind === "regenerate")!;
  expect(sent.body).toMatchObject({
    instructions: "make it longer, add a section on game-day specials",
  });
  expect(String(sent.body.idempotency_key)).toMatch(/^[0-9a-f-]{36}$/);
  expect(sent.body.brief_id).toMatch(/^[0-9a-f-]{36}$/);
  // The simulator answers with the new revision on the next read.
  await expect(page.locator("[data-revision]")).toHaveCount(2, {
    timeout: 20_000,
  });
  await expect(page.locator("[data-word-count]")).toHaveText("1,810 words");
  await expect(page.locator("[data-revision]").first()).toContainText(
    "Revision 2",
  );
  await expect(page).not.toHaveURL(/regenerating/);
});

test("a writing item opens to a designed Writing state, a failed one to its reason", async ({
  page,
}) => {
  await login(page, `${base}content/${WRITING}/`);
  await expect(
    page.getByRole("heading", { name: "Writing this draft" }),
  ).toBeVisible();
  await noRawText(page);
  await page.goto(`${base}content/${uuid(0xc3)}/`);
  await expect(page.getByRole("alert")).toContainText(
    "The draft was not long or well linked enough",
  );
  await page.getByRole("link", { name: "Try again" }).click();
  await expect(page.getByLabel("What should it be about?")).toHaveValue(
    "write a guide to game day parking near Miss B's",
  );
  await clean(page);
});

test("a landing page is reviewed to the same standard as an article", async ({
  page,
}) => {
  await login(page, `${base}content/${PAGE_ITEM}/`);
  await expect(page.getByText("Landing page", { exact: true })).toBeVisible();
  await expect(page.locator("[data-draft-summary]")).toBeVisible();
  await noRawText(page);
});
