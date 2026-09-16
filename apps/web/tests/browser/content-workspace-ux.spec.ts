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
    const agentAction = page.locator(
      'button[data-product-agent-workflow="agent.content"]',
    );
    await expect(agentAction).toHaveText("Run Content agent");
    await expect(
      page.locator('a[href="/automations?agent=agent.content"]'),
    ).toHaveCount(0);
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

  test("the actual Content workspace remains usable on a narrow viewport", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/content");
    await page.locator("#content-workspace").evaluate((element) => {
      (element as HTMLElement).hidden = false;
    });
    await expect(page.locator(".content-summary")).toBeVisible();
    await expect(page.locator(".content-filters")).toBeVisible();
    const widths = await page.evaluate(() => ({
      client: document.documentElement.clientWidth,
      scroll: document.documentElement.scrollWidth,
    }));
    expect(widths.scroll).toBeLessThanOrEqual(widths.client + 1);
  });
  test("client-rendered pipeline rows receive their card layout", async ({
    page,
  }) => {
    await page.goto("/content");
    const styles = await page.locator("#content-list").evaluate((region) => {
      const list = document.createElement("div");
      list.className = "content-list";
      const row = document.createElement("button");
      row.className = "content-row";
      const main = document.createElement("div");
      main.className = "content-row__main";
      main.append(
        document.createElement("strong"),
        document.createElement("span"),
      );
      const stage = document.createElement("div");
      stage.className = "content-row__stage";
      const next = document.createElement("div");
      next.className = "content-row__next";
      next.append(
        document.createElement("span"),
        document.createElement("strong"),
      );
      row.append(main, stage, next);
      list.append(row);
      region.append(list);

      const listStyle = getComputedStyle(list);
      const rowStyle = getComputedStyle(row);
      const nextStyle = getComputedStyle(next);
      return {
        listDisplay: listStyle.display,
        listGap: listStyle.gap,
        rowDisplay: rowStyle.display,
        rowRadius: rowStyle.borderRadius,
        rowColumns: rowStyle.gridTemplateColumns,
        nextBorderLeft: nextStyle.borderLeftWidth,
        nextBorderTop: nextStyle.borderTopWidth,
      };
    });

    expect(styles.listDisplay).toBe("grid");
    expect(styles.listGap).not.toBe("normal");
    expect(styles.rowDisplay).toBe("grid");
    expect(styles.rowRadius).not.toBe("0px");
    expect(styles.rowColumns).not.toBe("none");
    expect([styles.nextBorderLeft, styles.nextBorderTop]).toContain("1px");
  });
});
