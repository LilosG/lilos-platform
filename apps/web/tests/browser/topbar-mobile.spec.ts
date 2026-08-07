import { expect, test } from "@playwright/test";

// Regression: at viewport widths <=560px the shared global.css previously set
// `.topbar__actions { display: none }`, removing the organization switcher and
// sign-out from mobile users entirely. A separate 900px rule hid the sign-out
// button. Both are now removed; the topbar wraps its actions to a second row
// instead. These tests prove the controls remain in the DOM and not
// CSS-hidden at mobile widths, that the page does not overflow, and that
// primary content is not obscured.
//
// The build is unconfigured (no PUBLIC_LILOS_* env), so the controls keep
// their `hidden` HTML attributes (JS never unhides them). The tests therefore
// assert the CSS container is not `display: none` — the bug was a CSS rule
// that would have kept the controls invisible even after a configured build's
// JS removed the `hidden` attributes.

const MOBILE_VIEWPORTS = [
  { width: 390, height: 844 }, // small phone
  { width: 560, height: 900 }, // exact breakpoint boundary
  { width: 700, height: 900 }, // tablet, within the 900px rule
];

const PAGES = ["/", "/leads", "/insights"];

for (const viewport of MOBILE_VIEWPORTS) {
  for (const path of PAGES) {
    test(`topbar actions are not CSS-hidden at ${viewport.width}px on ${path}`, async ({
      page,
    }) => {
      await page.setViewportSize({
        width: viewport.width,
        height: viewport.height,
      });
      await page.goto(path);
      const display = await page
        .locator(".topbar__actions")
        .evaluate((el) => window.getComputedStyle(el).display);
      // The fix removed `display: none`; any other value (flex, etc.) is fine.
      expect(
        display,
        `.topbar__actions must not be display:none at ${viewport.width}px`,
      ).not.toBe("none");
    });

    test(`organization switcher and sign-out remain in the DOM at ${viewport.width}px on ${path}`, async ({
      page,
    }) => {
      await page.setViewportSize({
        width: viewport.width,
        height: viewport.height,
      });
      await page.goto(path);
      await expect(page.locator("#organization-switcher")).toBeAttached();
      await expect(page.locator("#sign-out-button")).toBeAttached();
    });

    test(`no horizontal document overflow at ${viewport.width}px on ${path}`, async ({
      page,
    }) => {
      await page.setViewportSize({
        width: viewport.width,
        height: viewport.height,
      });
      await page.goto(path);
      const dims = await page.evaluate(() => ({
        client: document.documentElement.clientWidth,
        scroll: document.documentElement.scrollWidth,
      }));
      expect(dims.scroll).toBeLessThanOrEqual(dims.client + 1);
    });

    test(`topbar does not obscure main content at ${viewport.width}px on ${path}`, async ({
      page,
    }) => {
      await page.setViewportSize({
        width: viewport.width,
        height: viewport.height,
      });
      await page.goto(path);
      // The topbar is position: sticky (in-flow), so it pushes main down
      // rather than overlapping it. Verify main's top is at or below the
      // topbar's bottom — i.e. no overlap.
      const overlap = await page.evaluate(() => {
        const topbar = document.querySelector(".topbar") as HTMLElement;
        const main = document.querySelector("main") as HTMLElement;
        if (!topbar || !main) return null;
        const topbarRect = topbar.getBoundingClientRect();
        const mainRect = main.getBoundingClientRect();
        return {
          topbarBottom: Math.round(topbarRect.bottom),
          mainTop: Math.round(mainRect.top),
          overlaps: mainRect.top < topbarRect.bottom,
        };
      });
      expect(overlap).not.toBeNull();
      expect(overlap!.overlaps).toBe(false);
    });
  }
}
