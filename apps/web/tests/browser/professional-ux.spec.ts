import { expect, test } from "@playwright/test";

// These tests validate the new platform-wide professional UX architecture:
// grouped sidebar navigation, settings directory, integrations directory,
// and the design-system shell consistency across all main routes.

test.describe("Professional UX shell", () => {
  test("workspace surfaces expose the shared loading, empty, failure, and success regions", async ({
    page,
  }) => {
    const surfaces = [
      ["/", "#workspace-content"],
      ["/gbp", "#gbp-content"],
      ["/reviews", "#reviews-content"],
      ["/leads", "#leads-content"],
      ["/content", "#content-workspace"],
      ["/seo", "#seo-content"],
      ["/automations", "#workspace-content"],
      ["/insights", "#insights-content"],
      ["/settings", "#settings-content"],
      ["/integrations", "#integrations-content"],
    ] as const;

    for (const [route, successRegion] of surfaces) {
      await page.goto(route);
      await expect(page.locator("#boot-loading")).toBeAttached();
      await expect(page.locator("#workspace-empty")).toBeAttached();
      await expect(page.locator("#boot-error")).toBeAttached();
      await expect(
        page.locator("#boot-error[role='alert'], #boot-error [role='alert']"),
      ).toHaveCount(1);
      await expect(page.locator(successRegion)).toBeAttached();
    }
  });

  test("sidebar navigation is grouped into sections", async ({ page }) => {
    await page.goto("/");
    const headings = await page
      .locator(".sidebar__group-heading")
      .allTextContents();
    expect(headings.length).toBeGreaterThanOrEqual(4);
    expect(headings).toContain("Workspace");
    expect(headings).toContain("Operations");
    expect(headings).toContain("Manage");
    expect(headings).toContain("Admin");
  });

  test("sidebar shows SVG icons for navigation items", async ({ page }) => {
    await page.goto("/");
    const icons = await page.locator(".sidebar__icon").count();
    expect(icons).toBeGreaterThan(0);
  });

  test("active navigation state is visually indicated", async ({ page }) => {
    await page.goto("/");
    const activeLink = page.locator('.sidebar__link[aria-current="page"]');
    await expect(activeLink).toHaveCount(1);
  });

  test("topbar shows organization context label", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator(".topbar__org-label")).toBeVisible();
    await expect(page.locator(".topbar__org-name")).toBeVisible();
  });

  test("every page has a page-head with eyebrow and title", async ({
    page,
  }) => {
    const routes = [
      "/",
      "/gbp",
      "/reviews",
      "/leads",
      "/content",
      "/seo",
      "/automations",
      "/insights",
      "/settings",
      "/integrations",
    ];
    for (const route of routes) {
      await page.goto(route);
      const eyebrow = page.locator(
        ".ui-page-header .ui-page-header__identity > .ui-overline",
      );
      const title = page.locator(".ui-page-header h1");
      const eyebrowCount = await eyebrow.count();
      const titleCount = await title.count();
      expect(
        eyebrowCount,
        `${route} should have an eyebrow`,
      ).toBeGreaterThanOrEqual(1);
      expect(titleCount, `${route} should have a title`).toBeGreaterThanOrEqual(
        1,
      );
    }
  });
});

test.describe("Settings directory", () => {
  test("settings page shows configuration domain cards", async ({ page }) => {
    await page.goto("/settings");
    // The not-configured state shows first, but the settings cards are inside
    // the hidden configured region, so we check they are attached.
    await expect(page.locator("#settings-content")).toBeAttached();
    const cards = page.locator("[data-domain]");
    await expect(cards).toHaveCount(6);
  });

  test("settings cards cover expected domains", async ({ page }) => {
    await page.goto("/settings");
    const domains = await page
      .locator("[data-domain]")
      .evaluateAll((els) => els.map((el) => el.getAttribute("data-domain")));
    expect(domains).toContain("business");
    expect(domains).toContain("locations");
    expect(domains).toContain("website");
    expect(domains).toContain("users");
    expect(domains).toContain("governance");
    expect(domains).toContain("products");
  });

  test("settings has a back button in the domain workspace", async ({
    page,
  }) => {
    await page.goto("/settings");
    await expect(page.locator("#back-to-settings")).toBeAttached();
  });
});

test.describe("Integrations directory", () => {
  test("integrations page has provider card container", async ({ page }) => {
    await page.goto("/integrations");
    await expect(page.locator("#integrations-content")).toBeAttached();
    await expect(page.locator("#integration-cards")).toBeAttached();
  });

  test("integrations page has a back button in the provider workspace", async ({
    page,
  }) => {
    await page.goto("/integrations");
    await expect(page.locator("#back-to-integrations")).toBeAttached();
  });
});

test.describe("GBP workspace tabs", () => {
  test("GBP workspace has tab navigation", async ({ page }) => {
    await page.goto("/gbp");
    const tabs = page.locator("#gbp-tabs .ui-tabs__tab");
    await expect(tabs).toHaveCount(5);
    const tabLabels = await tabs.allTextContents();
    expect(tabLabels).toEqual([
      "Overview",
      "Profile changes",
      "Special hours",
      "Posts",
      "Media records",
    ]);
  });
});

test.describe("SEO workspace tabs", () => {
  test("SEO workspace has tab navigation", async ({ page }) => {
    await page.goto("/seo");
    const tabs = page.locator("#seo-tabs .ui-tabs__tab");
    await expect(tabs).toHaveCount(4);
    const tabLabels = await tabs.allTextContents();
    expect(tabLabels).toEqual([
      "Overview",
      "Crawl",
      "Opportunities",
      "Search Console",
    ]);
  });
});

test.describe("Content workspace tabs", () => {
  test("Content workspace has tab navigation", async ({ page }) => {
    await page.goto("/content");
    const tabs = page.locator("#content-tabs .ui-tabs__tab");
    await expect(tabs).toHaveCount(3);
    const tabLabels = await tabs.allTextContents();
    expect(tabLabels).toEqual(["Pipeline", "Opportunities", "Publishing"]);
  });
});

test.describe("Onboarding stepper", () => {
  test("onboarding client workspace has a stepper", async ({ page }) => {
    await page.goto("/onboarding");
    await expect(page.locator("#onboarding-stepper")).toBeAttached();
    const steps = page.locator(".stepper__step");
    await expect(steps).toHaveCount(5);
    await expect(steps).toHaveText([
      /Client details/,
      /Source data/,
      /Products/,
      /Review/,
      /Activate/,
    ]);
  });
});

test.describe("Keyboard interaction", () => {
  test("tabs support arrow-key selection and complete ARIA relationships", async ({
    page,
  }) => {
    await page.goto("/content");
    await expect(
      page.getByRole("heading", { name: "This deployment is not configured" }),
    ).toBeVisible();
    // The browser suite intentionally runs without deployment credentials, so
    // configured workspace regions stay hidden. Reveal this region only to
    // exercise the attached tab interaction as it behaves after a real boot.
    await page.locator("#content-workspace").evaluate((element) => {
      (element as HTMLElement).hidden = false;
    });
    const first = page.locator('#content-tabs [role="tab"]').first();
    await first.focus();
    await page.keyboard.press("ArrowRight");
    const second = page.locator('#content-tabs [role="tab"]').nth(1);
    await expect(second).toBeFocused();
    await expect(second).toHaveAttribute("aria-selected", "true");
    const panelId = await second.getAttribute("aria-controls");
    expect(panelId).toBe("tab-opportunities");
    await expect(page.locator(`#${panelId}`)).toHaveAttribute(
      "role",
      "tabpanel",
    );
  });

  test("mobile navigation opens, closes with Escape, and exposes its state", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/");
    const toggle = page.locator("#mobile-navigation-toggle");
    await expect(toggle).toBeVisible();
    await toggle.click();
    await expect(toggle).toHaveAttribute("aria-expanded", "true");
    await expect(page.locator("#workspace-navigation-menu")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(toggle).toHaveAttribute("aria-expanded", "false");
  });
});

test.describe("Design system consistency", () => {
  test("metric cards use consistent class", async ({ page }) => {
    await page.goto("/");
    // In the not-configured state the metric-grid is inside hidden content
    await expect(page.locator(".ui-card-grid").first()).toBeAttached();
  });

  test("empty states use the design-system class", async ({ page }) => {
    await page.goto("/");
    // The workspace-empty region has an empty-state
    await expect(page.locator(".ui-empty-state").first()).toBeAttached();
  });
});
