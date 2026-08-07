import { expect, test } from "@playwright/test";

// Regression for the CSS specificity defect where a primary `.button` placed
// inside an `.attention-card` rendered white text on a white background
// because `.attention-card button` (specificity 0,1,1) overrode `.button`'s
// background to #fff without setting a color, leaving `.button`'s white text.

test("primary action button inside an attention-card is visibly styled, not white-on-white", async ({
  page,
}) => {
  await page.goto("/");
  // Inject the same structure the GBP page uses: a primary `.button` inside
  // an `.attention-card` container, styled only by the shared design system.
  const info = await page.evaluate(() => {
    const card = document.createElement("div");
    card.className = "attention-card";
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "button";
    btn.textContent = "Discover accounts and locations";
    card.append(btn);
    document.body.append(card);
    const styles = window.getComputedStyle(btn);
    return {
      background: styles.backgroundColor,
      color: styles.color,
    };
  });
  // The primary button must keep its green background (not be reset to white).
  expect(info.background).not.toBe("rgb(255, 255, 255)");
  // The text color must differ from the background so the label is visible.
  expect(info.color).not.toBe(info.background);
});
