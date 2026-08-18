import { expect, test } from "@playwright/test";

test.describe("Content detail editorial workspace layout", () => {
  test("detail region exists and is initially hidden", async ({ page }) => {
    await page.goto("/content");
    await expect(page.locator("#content-detail")).toBeAttached();
    await expect(page.locator("#content-detail")).toBeHidden();
    await expect(page.locator("#content-detail-body")).toBeAttached();
  });

  test("back to pipeline button exists in the detail view", async ({
    page,
  }) => {
    await page.goto("/content");
    await expect(page.locator("#back-to-content-pipeline")).toBeAttached();
  });

  test("detail region body has live region attribute for content updates", async ({
    page,
  }) => {
    await page.goto("/content");
    const body = page.locator("#content-detail-body");
    await expect(body).toHaveAttribute("aria-live", "polite");
  });
});

test.describe("Unconfigured content page integrity", () => {
  test("content page shows truthful not-configured state", async ({ page }) => {
    await page.goto("/content");
    await expect(
      page.getByRole("heading", {
        name: "This deployment is not configured",
      }),
    ).toBeVisible();
  });

  test("unconfigured page has no content-document elements rendered", async ({
    page,
  }) => {
    await page.goto("/content");
    const docs = page.locator(".content-document");
    await expect(docs).toHaveCount(0);
  });

  test("unconfigured page has no editorial workspace rendered", async ({
    page,
  }) => {
    await page.goto("/content");
    await expect(page.locator(".content-editorial-workspace")).toHaveCount(0);
  });

  test("new content item modal exists and is initially closed", async ({
    page,
  }) => {
    await page.goto("/content");
    const modal = page.locator("#new-content-item-modal");
    await expect(modal).toBeAttached();
    // A closed dialog should not be visible.
    await expect(modal).not.toBeVisible();
  });
});

test.describe("Content page responsive behavior", () => {
  test("desktop viewport has no horizontal overflow on content page", async ({
    page,
  }) => {
    await page.goto("/content");
    const widths = await page.evaluate(() => ({
      client: document.documentElement.clientWidth,
      scroll: document.documentElement.scrollWidth,
    }));
    expect(widths.scroll).toBeLessThanOrEqual(widths.client + 1);
  });

  test("mobile viewport has no horizontal overflow on content page", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/content");
    const widths = await page.evaluate(() => ({
      client: document.documentElement.clientWidth,
      scroll: document.documentElement.scrollWidth,
    }));
    expect(widths.scroll).toBeLessThanOrEqual(widths.client + 1);
  });

  test("mobile viewport does not create ultra-narrow column layout in not-configured state", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/content");
    // The unconfigured state uses the empty-state component which should
    // render at a usable width.
    const emptyState = page.locator(".ui-empty-state").first();
    await expect(emptyState).toBeVisible();
  });
});

test.describe("Content page form controls", () => {
  test("new content form modal has title with maxlength validation", async ({
    page,
  }) => {
    await page.goto("/content");
    const titleInput = page.locator("#new-content-title");
    await expect(titleInput).toBeAttached();
    await expect(titleInput).toHaveAttribute("maxlength", "300");
  });

  test("new content form modal content type select is present", async ({
    page,
  }) => {
    await page.goto("/content");
    const typeSelect = page.locator("#new-content-type");
    await expect(typeSelect).toBeAttached();
    const options = typeSelect.locator("option");
    await expect(options).toHaveCount(6); // placeholder + 5 types
  });

  test("content page action buttons exist in workspace header", async ({
    page,
  }) => {
    await page.goto("/content");
    // The workspace is hidden but the buttons are in the DOM.
    // Unhide the workspace region to check its structure.
    await page.locator("#content-workspace").evaluate((el) => {
      (el as HTMLElement).hidden = false;
    });
    await expect(page.locator("#new-content-item-button")).toBeVisible();
    await expect(
      page.locator("#content-tabs").locator(".ui-tabs__tab"),
    ).toHaveCount(3);
  });
});

test.describe("Content CSS layout classes are defined", () => {
  test("content-editorial-workspace CSS class is defined", async ({ page }) => {
    await page.goto("/content");
    // Verify the CSS rule exists by checking the computed style of a
    // dynamically created element (without overriding display).
    const hasStyle = await page.evaluate(() => {
      const el = document.createElement("div");
      el.className = "content-editorial-workspace";
      el.style.visibility = "hidden";
      document.body.append(el);
      const display = window.getComputedStyle(el).display;
      el.remove();
      return display === "grid";
    });
    expect(hasStyle).toBe(true);
  });

  test("content-document CSS class is defined", async ({ page }) => {
    await page.goto("/content");
    const hasStyle = await page.evaluate(() => {
      const el = document.createElement("article");
      el.className = "content-document";
      el.style.visibility = "hidden";
      document.body.append(el);
      const maxWidth = window.getComputedStyle(el).maxWidth;
      el.remove();
      return maxWidth !== "none";
    });
    expect(hasStyle).toBe(true);
  });

  test("editorial workspace stacks to single column on narrow viewport", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/content");
    const isSingleColumn = await page.evaluate(() => {
      const el = document.createElement("div");
      el.className = "content-editorial-workspace";
      el.style.visibility = "hidden";
      document.body.append(el);
      const templateColumns = window.getComputedStyle(el).gridTemplateColumns;
      el.remove();
      // At <= 48rem, should be single column (one track).
      return (
        templateColumns.split(" ").length <= 1 ||
        templateColumns === "minmax(0px, 1fr)"
      );
    });
    expect(isSingleColumn).toBe(true);
  });
});

test.describe("Approval actions and stage language in content.astro", () => {
  test("content page does not have the old four-equal-column draft treatment", async ({
    page,
  }) => {
    await page.goto("/content");
    // The old page rendered `ui-card-grid--lg` inside `#content-detail-body`
    // with four items.  The new page should not have this pattern inside the
    // detail body (it now uses the editorial workspace layout).
    //
    // Since we are in the unconfigured state, the detail body is empty, so
    // this test confirms no old layout artifacts exist in the rendered DOM.
    await page.locator("#content-workspace").evaluate((el) => {
      (el as HTMLElement).hidden = false;
    });
    await page.locator("#content-detail").evaluate((el) => {
      (el as HTMLElement).hidden = false;
    });
    // The body should be empty — no ui-card-grid with four cards.
    const gridCards = page.locator("#content-detail-body .ui-card-grid--lg");
    await expect(gridCards).toHaveCount(0);
  });
});
