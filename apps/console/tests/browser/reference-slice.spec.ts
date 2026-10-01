import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
const root = "/clients/synthetic-alpha/opportunities/";
const detail = root + "33333333-3333-4333-8333-333333333333/";
async function login(
  page: import("@playwright/test").Page,
  email = "a@example.test",
) {
  await page.goto(`/login/?return=${encodeURIComponent(root)}`);
  await page.getByLabel("Email", { exact: true }).fill(email);
  await page.getByLabel("Password", { exact: true }).fill("synthetic-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
}
test("SSR login -> canonical detail -> MFA -> revise -> exact approve -> publication proof", async ({
  page,
  context,
}) => {
  await login(page);
  await expect(
    page.getByRole("heading", { name: "Opportunities", exact: true }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Details", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Evidence", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("Deterministic quality: passed", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Approve exact revision 1" }),
  ).toBeDisabled();
  const cookies = await context.cookies();
  expect(
    cookies
      .filter((c) => c.name.startsWith("lilos-session"))
      .every((c) => c.httpOnly && c.sameSite === "Lax"),
  ).toBe(true);
  expect(await page.content()).not.toContain("refresh-");
  const before = new AxeBuilder({ page });
  expect((await before.analyze()).violations).toEqual([]);
  await page
    .getByRole("link", {
      name: "Verify authenticator to request approval access",
    })
    .click();
  await page.getByRole("button", { name: "Set up authenticator" }).click();
  await expect(page.getByText(/Setup key:/)).toBeVisible();
  await page.getByLabel("Authenticator code").fill("000000");
  await page.getByRole("button", { name: "Verify", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText(
    "Invalid authenticator code",
  );
  // Abandoned unverified enrollment is removed before a new enrollment, never treated as verified.
  await page.getByRole("button", { name: "Set up authenticator" }).click();
  await page.getByLabel("Authenticator code").fill("123456");
  await page.getByRole("button", { name: "Verify", exact: true }).click();
  await expect(page).toHaveURL(new RegExp(detail));
  // Reuse the verified factor for step-up, without creating another enrollment.
  const elevated = (await context.cookies()).find(
    (cookie) => cookie.name === "lilos-session",
  )!;
  const stored = JSON.parse(
    Buffer.from(
      decodeURIComponent(elevated.value).slice(7),
      "base64url",
    ).toString(),
  );
  const claims = JSON.parse(
    Buffer.from(stored.access_token.split(".")[1], "base64url").toString(),
  );
  claims.aal = "aal1";
  stored.access_token = [
    stored.access_token.split(".")[0],
    Buffer.from(JSON.stringify(claims)).toString("base64url"),
    "c3ludGhldGljLXNpZ25hdHVyZQ",
  ].join(".");
  await context.addCookies([
    {
      ...elevated,
      value:
        "base64-" + Buffer.from(JSON.stringify(stored)).toString("base64url"),
    },
  ]);
  await page.goto(`/mfa/?return=${encodeURIComponent(detail)}`);
  await expect(
    page.getByRole("button", { name: "Set up authenticator" }),
  ).toHaveCount(0);
  await page.getByLabel("Authenticator code").fill("123456");
  await page.getByRole("button", { name: "Verify", exact: true }).click();
  await expect(page).toHaveURL(new RegExp(detail));
  await page
    .getByRole("textbox", { name: "meta_description", exact: true })
    .fill(
      "An edited synthetic description for this exact page and audited revision.",
    );
  await page.getByRole("button", { name: "Save new revision" }).click();
  await expect(
    page.getByRole("heading", {
      name: "Recommendation revision 2",
      exact: true,
    }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Approve exact revision 2" }).click();
  await expect(
    page.getByText("Live verification observed: 2026-09-30T00:00:00Z", {
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Open pull request" }),
  ).toBeVisible();
  await expect(page.getByText(/Deployment: ready/)).toBeVisible();
  await expect(page.getByText(/Implementation: verified/)).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.screenshot({
    path: `test-results/reference-${test.info().project.name}.png`,
    fullPage: true,
  });
  await page.goto(root);
  if (test.info().project.name === "mobile")
    await page.getByRole("button", { name: "Toggle navigation" }).click();
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/login\//);
  expect(
    (await context.cookies()).filter((c) => c.name.startsWith("lilos-session")),
  ).toHaveLength(0);
});
test("tenant SSR/BFF/cache isolation and direct unauthorized source requests", async ({
  browser,
}) => {
  const a = await browser.newContext({ baseURL: "http://127.0.0.1:4346" });
  const b = await browser.newContext({ baseURL: "http://127.0.0.1:4346" });
  const pa = await a.newPage();
  const pb = await b.newPage();
  await login(pa);
  await pa.goto(detail);
  await expect(
    pa.getByRole("heading", { name: "Evidence", exact: true }),
  ).toBeVisible();
  await login(pb, "b@example.test");
  const result = await pb.goto(detail);
  expect(result?.status()).toBe(404);
  expect(await pb.content()).not.toContain("Synthetic Alpha");
  const denied = await b.request.get(
    "/api/organizations/11111111-1111-4111-8111-111111111111/command-center/opportunities/",
  );
  expect(denied.status()).toBe(404);
  expect(await denied.text()).not.toContain("Synthetic Alpha");
  expect(denied.headers()["cache-control"]).toBe("private, no-store");
  const forged = await b.request.post(
    "/api/organizations/22222222-2222-4222-8222-222222222222/seo/recommendations/55555555-5555-4555-8555-555555555555/decision/",
    {
      headers: {
        origin: "https://evil.test",
        "Content-Type": "application/json",
      },
      data: { approve: true },
    },
  );
  expect(forged.status()).toBe(403);
  await a.close();
  await b.close();
});
test("attention entries use the same canonical detail route", async ({
  page,
}) => {
  await login(page);
  await page.goto("/clients/synthetic-alpha/attention/");
  await page
    .getByRole("link", { name: "waiting approval", exact: true })
    .click();
  await expect(page).toHaveURL(new RegExp(detail));
});

for (const order of ["fast", "slow"]) {
  test(`distributed stale refresh response cannot clear rotated cookies (${order})`, async ({
    page,
    context,
  }) => {
    await login(page);
    const jar = await context.cookies();
    const cookie = jar.find((cookie) => cookie.name === "lilos-session")!;
    const raw = JSON.parse(
      Buffer.from(
        decodeURIComponent(cookie.value).slice(7),
        "base64url",
      ).toString(),
    );
    const payload = JSON.parse(
      Buffer.from(raw.access_token.split(".")[1], "base64url").toString(),
    );
    payload.exp = Math.floor(Date.now() / 1000) - 20;
    raw.access_token = [
      raw.access_token.split(".")[0],
      Buffer.from(JSON.stringify(payload)).toString("base64url"),
      "c3ludGhldGljLXNpZ25hdHVyZQ",
    ].join(".");
    raw.expires_at = payload.exp;
    raw.refresh_token = `race-${crypto.randomUUID()}-${order}`;
    await context.addCookies([
      {
        ...cookie,
        value:
          "base64-" + Buffer.from(JSON.stringify(raw)).toString("base64url"),
      },
    ]);
    const outcomes = await page.evaluate(async () =>
      Promise.all(
        [1, 2].map(async () => {
          const response = await fetch("/api/me/organizations/");
          return response.status;
        }),
      ),
    );
    expect(outcomes.sort()).toEqual([200, 401]);
    const after = await context.cookies();
    expect(
      after.some(
        (cookie) =>
          cookie.name.startsWith("lilos-session") && cookie.value.length > 0,
      ),
    ).toBe(true);
    const response = await page.goto(root);
    expect(response?.status()).toBe(200);
    await expect(
      page.getByRole("heading", { name: "Opportunities", exact: true }),
    ).toBeVisible();
  });
}
