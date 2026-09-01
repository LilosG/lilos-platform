import { expect, test, type Page } from "@playwright/test";

const fixedNow = new Date("2026-08-14T20:30:00-07:00").valueOf();

async function openFixture(
  page: Page,
  route: string,
  readySelector: string,
): Promise<void> {
  await page.addInitScript((now) => {
    const NativeDate = Date;
    class FixtureDate extends NativeDate {
      constructor(value?: string | number | Date) {
        super(value === undefined ? now : value);
      }

      static now(): number {
        return now;
      }
    }
    globalThis.Date = FixtureDate as DateConstructor;
  }, fixedNow);

  await page.goto(
    `/evidence-session?next=${encodeURIComponent(route)}&mode=full`,
  );
  await expect(page.locator(readySelector)).toBeVisible();
  await expect(page.locator("[data-packet-4-evidence-caption]")).toBeVisible();
}

const surfaces = [
  {
    name: "overview",
    route: "/",
    ready: "#workspace-content",
    settled: "#kpi-grid .ui-metric-card__label",
    settledText: "Managed locations",
  },
  {
    name: "business-profile",
    route: "/gbp",
    ready: "#gbp-content",
    settled: "#location-picker-panel .ui-table",
  },
  {
    name: "reviews",
    route: "/reviews",
    ready: "#reviews-content",
    settled: "#review-stages-all-count",
    settledText: "90",
  },
  {
    name: "leads",
    route: "/leads",
    ready: "#leads-content",
    settled: "#leads-list .ui-table",
  },
  {
    name: "content",
    route: "/content",
    ready: "#content-workspace",
    settled: "#content-stages-all-count",
    settledText: "3",
  },
  {
    name: "seo",
    route: "/seo",
    ready: "#seo-content",
    settled: "#seo-metrics .ui-metric-card",
  },
  {
    name: "automations",
    route: "/automations",
    ready: "#workspace-content",
    settled: "#workflow-catalog .ui-table",
  },
  {
    name: "insights",
    route: "/insights",
    ready: "#insights-content",
    settled: "#website-performance-panel canvas",
  },
  {
    name: "settings",
    route: "/settings",
    ready: "#settings-content",
    settled: "#settings-cards [data-domain]",
  },
  {
    name: "integrations",
    route: "/integrations",
    ready: "#integrations-content",
    settled: "#integration-cards [data-provider]",
  },
] as const;

for (const surface of surfaces) {
  test(`${surface.name} matches its design-system baseline`, async ({
    page,
  }) => {
    await openFixture(page, surface.route, surface.ready);
    const settled = page.locator(surface.settled).first();
    await expect(settled).toBeVisible();
    if ("settledText" in surface) {
      await expect(settled).toHaveText(surface.settledText);
    }
    if (surface.name === "seo") {
      await page.getByRole("tab", { name: "Search Console" }).click();
      const chart = page.locator("#tab-search-console canvas");
      await expect(chart).toBeVisible();
      await chart.scrollIntoViewIfNeeded();
    }
    await expect(page).toHaveScreenshot(`${surface.name}.png`, {
      animations: "disabled",
      caret: "hide",
      scale: "css",
    });
  });
}

test("onboarding fixture exposes the source-first activation path", async ({
  page,
}) => {
  await openFixture(
    page,
    "/onboarding?org=org-packet-4",
    "#onboarding-content",
  );
  await expect(page.locator("#progress-label")).toHaveText("83% complete");
  await expect(
    page.getByText("Source data", { exact: true }).first(),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Start or retry website crawl" }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: /Connect or map Google/i }),
  ).toBeVisible();
  await expect(page.locator("#blockers-panel")).toContainText(
    "Before activation, finish these core details",
  );
});
