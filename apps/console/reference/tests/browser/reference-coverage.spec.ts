import { writeFileSync, mkdirSync } from "node:fs";
import { test, expect } from "@playwright/test";
import { clients } from "../../src/data/fixtures/clients";
import {
  clientNavigation,
  localTabs,
  websiteTabs,
  route,
} from "../../src/config/routes";
const normalize = (s: string) => s.replace(/\s+/g, " ").trim();
test("every client screen preserves Revision 10 visible data and content", async ({
  page,
  context,
}) => {
  test.setTimeout(240000);
  const reference = await context.newPage();
  const differences: { path: string; reference: string; astro: string }[] = [];
  for (const client of clients)
    for (const group of clientNavigation)
      for (const [area] of group.items)
        for (const section of area === "Local Search"
          ? localTabs
          : area === "Website & Content"
            ? websiteTabs
            : ["Overview"]) {
          const path = route("client", client.id, area, section);
          await Promise.all([
            page.goto(path, { waitUntil: "domcontentloaded" }),
            reference.goto(
              "http://127.0.0.1:8000/#client/" +
                client.id +
                "/" +
                encodeURIComponent(area) +
                "/" +
                encodeURIComponent(section),
              { waitUntil: "domcontentloaded" },
            ),
          ]);
          const original = normalize(
            await reference.locator("main").innerText(),
          );
          const converted = normalize(await page.locator("main").innerText());
          if (original !== converted)
            differences.push({ path, reference: original, astro: converted });
        }
  mkdirSync("artifacts/visual", { recursive: true });
  writeFileSync(
    "artifacts/visual/content-coverage.json",
    JSON.stringify({ compared: 228, differences }, null, 2),
  );
  expect(differences.map((d) => d.path)).toEqual([]);
});

import { opportunities } from "../../src/data/fixtures/opportunities";
test("all canonical Opportunity details preserve their reference evidence", async ({
  page,
  context,
}) => {
  const reference = await context.newPage();
  await reference.goto("http://127.0.0.1:8000/#opportunities");
  await page.goto("/opportunities/");
  for (const opportunity of opportunities) {
    await reference
      .locator(`button[onclick="openOpp(${opportunity.id})"]`)
      .click();
    await page
      .locator(`main [data-opportunity-id="${opportunity.id}"] button`)
      .click();
    expect(
      normalize(await page.getByRole("dialog").innerText()),
      String(opportunity.id),
    ).toBe(normalize(await reference.locator("dialog").innerText()));
    await page.keyboard.press("Escape");
    await reference.keyboard.press("Escape");
  }
});
