import { defineConfig, devices } from "@playwright/test";

/**
 * Production acceptance configuration.
 *
 * Targets the live Vercel deployment at https://lilos-platform-web.vercel.app.
 * NEVER runs against local preview. Uses a manually bootstrapped storageState
 * file so acceptance checks can reuse one operator session.
 *
 * Usage:
 *   1. Bootstrap auth (one-time, headed):
 *      LILOS_PRODUCTION_ACCEPTANCE_ORG_NAME="<organization>" npm run production:auth
 *
 *   2. Run the active production acceptance canary:
 *      npm run production:test
 *
 * The active production project intentionally matches only the native Hermes
 * read-only acceptance spec. The older broad acceptance.spec.ts contains
 * historical client-specific assumptions and is excluded from production
 * execution until it is fully generalized. This prevents a stale tenant name
 * from ever selecting or mutating a production client.
 *
 * The acceptance project does NOT depend on auth-setup. If the storageState
 * file is missing, the acceptance run fails with a clear instruction to run
 * `npm run production:auth` first.
 */

export default defineConfig({
  testDir: "./tests/production",
  outputDir: "./.playwright-production-output",
  reporter: [
    ["line"],
    ["html", { outputFolder: "./playwright-production-report" }],
  ],
  retries: 0,
  timeout: 120_000,
  expect: { timeout: 20_000 },

  use: {
    baseURL: "https://lilos-platform-web.vercel.app",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },

  projects: [
    // ── Auth bootstrap (manual, headed, one-time) ──────────────────────
    {
      name: "auth-setup",
      testMatch: /auth\.setup\.ts/,
      use: {
        ...devices["Desktop Chrome"],
        channel: "chrome",
        launchOptions: { headless: false },
      },
    },

    // ── Production acceptance (reuses saved auth state) ────────────────
    // Only the tenant-generic, read-only Hermes canary is active here.
    {
      name: "production-acceptance",
      testMatch: /hermes\.acceptance\.spec\.ts/,
      use: {
        ...devices["Desktop Chrome"],
        channel: "chrome",
        viewport: { width: 1440, height: 900 },
        storageState: ".auth/production-state.json",
      },
    },
  ],
});
