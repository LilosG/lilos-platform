// Renders the client report document to a PDF with the browser's own print engine, the way
// "Download PDF" does, so the pages can be read as images.
//
//   node scripts/render-report-pdf.mjs <scenario> <client> <period> <out.pdf> [revision]
//
// The scenario is a mode of the synthetic report simulator (tests/browser/report-sim.mjs); the
// console and the simulator must already be running (see playwright.config.ts for their env).
import { chromium } from "@playwright/test";
const [scenario, client, period, out, revision] = process.argv.slice(2);
if (!out) throw new Error("usage: render-report-pdf.mjs scenario client period out.pdf");
const consoleUrl = process.env.CONSOLE ?? "http://127.0.0.1:4346";
const sim = consoleUrl.replace("4346", "4455");
await fetch(`${sim}/test/reports-scenario`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ mode: scenario }),
});
const browser = await chromium.launch(
  process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE
    ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE }
    : {},
);
const page = await browser.newPage({ viewport: { width: 1000, height: 1200 } });
const target = `/clients/${client}/reports/${period}/document/${revision ? `?revision=${revision}` : ""}`;
await page.goto(`${consoleUrl}/login/?return=${encodeURIComponent(target)}`);
await page.getByLabel("Email", { exact: true }).fill("admin@example.test");
await page.getByLabel("Password", { exact: true }).fill("synthetic-password");
await page.getByRole("button", { name: "Sign in", exact: true }).click();
await page.waitForSelector("article.doc");
await page.evaluate(() => document.fonts.ready);
await page.emulateMedia({ media: "print" });
await page.pdf({ path: out, preferCSSPageSize: true, printBackground: true });
await browser.close();
