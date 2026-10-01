import { test, expect } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";
const screens = [
  ["portfolio-dashboard", "/", "#dashboard"],
  ["clients", "/clients/", "#clients"],
  ["portfolio-opportunities", "/opportunities/", "#opportunities"],
  ["reports", "/reports/", "#reports"],
  ["automations", "/automations/", "#automations"],
  ["integrations", "/integrations/", "#integrations"],
  [
    "client-overview",
    "/clients/coco-maya/",
    "#client/coco-maya/Overview/Overview",
  ],
  [
    "local-search",
    "/clients/coco-maya/local-search/",
    "#client/coco-maya/Local%20Search/Overview",
  ],
  [
    "rankings",
    "/clients/coco-maya/local-search/rankings/",
    "#client/coco-maya/Local%20Search/Rankings",
  ],
  [
    "gbp",
    "/clients/coco-maya/local-search/google-business-profile/",
    "#client/coco-maya/Local%20Search/Google%20Business%20Profile",
  ],
  [
    "reviews",
    "/clients/coco-maya/reviews/",
    "#client/coco-maya/Reviews/Overview",
  ],
  [
    "website-content",
    "/clients/coco-maya/website-content/",
    "#client/coco-maya/Website%20%26%20Content/Overview",
  ],
  [
    "conversions",
    "/clients/coco-maya/website-content/conversions/",
    "#client/coco-maya/Website%20%26%20Content/Conversions",
  ],
  ["leads", "/clients/coco-maya/leads/", "#client/coco-maya/Leads/Overview"],
  [
    "client-opportunities",
    "/clients/coco-maya/opportunities/",
    "#client/coco-maya/Opportunities/Overview",
  ],
] as const;
for (const [name, path, hash] of screens)
  test(`visual parity: ${name}`, async ({ page, context }, testInfo) => {
    const reference = await context.newPage();
    await reference.goto("http://127.0.0.1:8000/" + hash);
    await page.goto(path);
    await Promise.all([
      page.evaluate(() => document.fonts.ready),
      reference.evaluate(() => document.fonts.ready),
    ]);
    const normalize = (s: string) => s.replace(/\s+/g, " ").trim();
    const original = normalize(await reference.locator("main").innerText());
    const converted = normalize(await page.locator("main").innerText());
    const dir = "artifacts/visual";
    mkdirSync(dir, { recursive: true });
    await reference.screenshot({
      path: `${dir}/${name}-reference.png`,
      fullPage: true,
    });
    await page.screenshot({ path: `${dir}/${name}-astro.png`, fullPage: true });
    const geometry = async (p: typeof page) =>
      p
        .locator(
          "main .pagehead, main .metrics, main .grid, main .panel, main .snapshot, main .sectiontabs, main .snapshotmetric > span, main .snapshotmetric > strong, main .snapshotmetric > small",
        )
        .evaluateAll((elements) =>
          elements
            .map((el) => {
              const r = el.getBoundingClientRect();
              return {
                class: el.className,
                x: r.x,
                y: r.y,
                width: r.width,
                height: r.height,
              };
            })
            .filter((r) => r.width > 0),
        );
    const tabTypography = async (p: typeof page) =>
      p.locator("main .sectiontabs > *").evaluateAll((tabs) =>
        tabs.map((tab) => {
          const style = getComputedStyle(tab);
          return {
            weight: style.fontWeight,
            size: style.fontSize,
            family: style.fontFamily,
          };
        }),
      );
    expect(await tabTypography(page)).toEqual(await tabTypography(reference));
    const before = await geometry(reference),
      after = await geometry(page);
    writeFileSync(
      `${dir}/${name}.json`,
      JSON.stringify(
        {
          viewport: { width: 1440, height: 1000 },
          textMatches: original === converted,
          original,
          converted,
          before,
          after,
        },
        null,
        2,
      ),
    );
    await testInfo.attach(name, {
      path: `${dir}/${name}-astro.png`,
      contentType: "image/png",
    });
    expect(converted).toBe(original);
    expect(
      after.map(({ x, y, width, height }) => ({ x, y, width, height })),
    ).toEqual(
      before.map(({ x, y, width, height }) => ({ x, y, width, height })),
    );
  });
test("visual parity: opportunity detail", async ({ page, context }) => {
  const ref = await context.newPage();
  await ref.goto(
    "http://127.0.0.1:8000/#client/coco-maya/Opportunities/Overview",
  );
  await page.goto("/clients/coco-maya/opportunities/");
  await ref.locator('button[onclick="openOpp(13)"]').click();
  await page.locator('main [data-opportunity-id="13"] button').click();
  await Promise.all([
    page.evaluate(() => document.fonts.ready),
    ref.evaluate(() => document.fonts.ready),
  ]);
  mkdirSync("artifacts/visual", { recursive: true });
  await ref.screenshot({
    path: "artifacts/visual/opportunity-detail-reference.png",
  });
  await page.screenshot({
    path: "artifacts/visual/opportunity-detail-astro.png",
  });
  expect(
    (await page.getByRole("dialog").innerText()).replace(/\s+/g, " ").trim(),
  ).toBe((await ref.locator("dialog").innerText()).replace(/\s+/g, " ").trim());
});
