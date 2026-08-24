import { expect, test } from "@playwright/test";

test("inline confirmation stacks without overlap at narrow widths", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/integrations");
  await page.locator("body").evaluate((body) => {
    const prompt = document.createElement("div");
    prompt.id = "confirmation-layout-regression";
    prompt.className = "ui-notice ui-notice--warning ui-confirm-inline";
    const message = document.createElement("p");
    message.className = "ui-confirm-inline__message";
    message.textContent =
      "Enable provider writes only after checking every governed mapping and approval requirement.";
    const actions = document.createElement("div");
    actions.className = "ui-confirm-inline__actions";
    for (const [label, tone] of [
      ["Confirm", "danger"],
      ["Cancel", "secondary"],
    ]) {
      const button = document.createElement("button");
      button.className = `ui-button ui-button--${tone} ui-button--sm`;
      button.textContent = label;
      actions.append(button);
    }
    prompt.append(message, actions);
    body.append(prompt);
  });

  const prompt = page.locator("#confirmation-layout-regression");
  await expect(prompt).toBeVisible();
  const boxes = await prompt.evaluate((element) => {
    const message = element.querySelector(".ui-confirm-inline__message")!;
    const actions = element.querySelector(".ui-confirm-inline__actions")!;
    const messageBox = message.getBoundingClientRect();
    const actionsBox = actions.getBoundingClientRect();
    return {
      messageBottom: messageBox.bottom,
      actionsTop: actionsBox.top,
      documentWidth: document.documentElement.scrollWidth,
      viewportWidth: document.documentElement.clientWidth,
    };
  });

  expect(boxes.actionsTop).toBeGreaterThanOrEqual(boxes.messageBottom);
  expect(boxes.documentWidth).toBeLessThanOrEqual(boxes.viewportWidth);
});
