import { expect, test } from "@playwright/test";

const routes = [
  ["/", "#workspace-content"],
  ["/gbp", "#gbp-content"],
  ["/seo", "#seo-content"],
  ["/content", "#content-workspace"],
  ["/reviews", "#reviews-content"],
  ["/automations", "#workspace-content"],
] as const;

for (const width of [1440, 1024, 420, 390]) {
  test(`product workspaces fit ${width}px`, async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.setViewportSize({ width, height: 900 });
    for (const [route, ready] of routes) {
      await page.goto(
        `/evidence-session?next=${encodeURIComponent(route)}&mode=full`,
      );
      await page.waitForURL((url) => url.pathname === route);
      await expect(page.locator(ready)).toBeVisible();
      await expect
        .poll(() =>
          page.evaluate(
            () => document.documentElement.scrollWidth - window.innerWidth,
          ),
        )
        .toBeLessThanOrEqual(1);
      expect(errors, `${route} console errors`).toEqual([]);
    }
  });
}
