// Captures the client report document sections at 1440px and 390px. The document has no
// reference screen, so each section is shown on its own.
//
//   CONSOLE=http://127.0.0.1:4346 node scripts/capture-report-document.mjs
import { mkdir } from "node:fs/promises";
import { chromium } from "@playwright/test";
const consoleUrl = process.env.CONSOLE ?? "http://127.0.0.1:4346";
const sim = consoleUrl.replace("4346", "4455");
const out = new URL("../visual/step-10b-report-redesign/", import.meta.url);
const sections = [
  ["document-cover", ".cover"],
  ["document-at-a-glance", "[data-section=glance]"],
  ["document-scorecard", "[data-section=scorecard]"],
  ["document-chart-page", "[data-section=gbp]"],
  ["document-search-page", "[data-section=search]"],
  ["document-notes", "[data-section=notes]"],
];
await mkdir(out, { recursive: true });
await fetch(`${sim}/test/reports-scenario`, {
  method: "POST",
  body: JSON.stringify({ mode: "gaps" }),
});
const browser = await chromium.launch(
  process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE
    ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE }
    : {},
);
for (const [label, width] of [
  ["desktop", 1440],
  ["mobile", 390],
]) {
  const page = await browser.newPage({ viewport: { width, height: 1000 } });
  const target = "/clients/synthetic-alpha/reports/2026-05_2026-09/document/";
  await page.goto(`${consoleUrl}/login/?return=${encodeURIComponent(target)}`);
  await page.getByLabel("Email", { exact: true }).fill("admin@example.test");
  await page.getByLabel("Password", { exact: true }).fill("synthetic-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.waitForSelector("article.doc");
  for (const [name, selector] of sections)
    await page
      .locator(selector)
      .first()
      .screenshot({
        path: new URL(`${name}-${label}.png`, out).pathname,
      });
  await page.close();
}
await browser.close();
