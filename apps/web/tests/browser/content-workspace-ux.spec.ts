import { expect, test } from "@playwright/test";

test.describe("Content operator workflow", () => {
  test("unconfigured deployment shows an honest empty state", async ({
    page,
  }) => {
    await page.goto("/content");
    await expect(
      page.getByRole("heading", { name: "This deployment is not configured" }),
    ).toBeVisible();
    await expect(page.locator("#content-workspace")).toBeHidden();
    await expect(page.locator("#content-list")).toBeEmpty();
  });

  test("pipeline and detail are separate regions with a way back", async ({
    page,
  }) => {
    await page.goto("/content");
    await expect(page.locator("#content-list-view")).toBeAttached();
    await expect(page.locator("#content-detail-view")).toBeHidden();
    await expect(page.locator("#content-detail")).toHaveAttribute(
      "aria-live",
      "polite",
    );
    await expect(page.locator("#back-to-list")).toHaveText(/Back to content/);
  });

  test("new item dialog is closed and validates the entered content", async ({
    page,
  }) => {
    await page.goto("/content");
    const modal = page.locator("#new-item-modal");
    await expect(modal).toBeAttached();
    await expect(modal).not.toBeVisible();
    await expect(page.locator("#content-title")).toHaveAttribute(
      "maxlength",
      "300",
    );
    await expect(page.locator("#content-slug")).toHaveAttribute(
      "maxlength",
      "200",
    );
    await expect(page.locator("#content-type option")).toHaveCount(4);
    await expect(page.locator("#content-location option")).toHaveCount(1);
  });

  test("header offers creation and the governed Content agent", async ({
    page,
  }) => {
    await page.goto("/content");
    await expect(page.locator("#new-item")).toHaveText("New content item");
    await expect(
      page.locator('a[href="/automations?agent=agent.content"]'),
    ).toHaveText("Run Content agent");
    await expect(page.locator(".content-filters button")).toHaveText([
      "Active",
      "Publishing",
      "Published",
      "All",
    ]);
  });

  test("empty deployment does not invent a content document", async ({
    page,
  }) => {
    await page.goto("/content");
    await expect(page.locator(".content-document")).toHaveCount(0);
    await expect(page.locator(".content-editorial-workspace")).toHaveCount(0);
  });

  test("content layout does not overflow on desktop or mobile", async ({
    page,
  }) => {
    for (const width of [1280, 390]) {
      await page.setViewportSize({ width, height: 844 });
      await page.goto("/content");
      const widths = await page.evaluate(() => ({
        client: document.documentElement.clientWidth,
        scroll: document.documentElement.scrollWidth,
      }));
      expect(widths.scroll).toBeLessThanOrEqual(widths.client + 1);
      await expect(page.locator(".ui-empty-state").first()).toBeVisible();
    }
  });

  test("editorial document styles remain readable on a narrow viewport", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/content");
    const styles = await page.evaluate(() => {
      const workspace = document.createElement("div");
      workspace.className = "content-editorial-workspace";
      const documentBody = document.createElement("article");
      documentBody.className = "content-document";
      document.body.append(workspace, documentBody);
      const display = getComputedStyle(workspace).display;
      const columns = getComputedStyle(workspace).gridTemplateColumns;
      const maxWidth = getComputedStyle(documentBody).maxWidth;
      workspace.remove();
      documentBody.remove();
      return { display, columns, maxWidth };
    });
    expect(styles.display).toBe("grid");
    expect(styles.columns.split(" ")).toHaveLength(1);
    expect(styles.maxWidth).not.toBe("none");
  });
});
