import { defineConfig, devices } from "@playwright/test";

/**
 * Production acceptance configuration.
 *
 * Targets the live Vercel deployment at https://lilos-platform-web.vercel.app.
 * NEVER runs against local preview.  Uses a manually-bootstrapped storageState
 * file so acceptance checks can reuse one operator session.
 *
 * Usage:
 *   1. Bootstrap auth (one-time, headed):
 *      npm run production:auth
 *
 *   2. Run acceptance (reuses saved auth state):
 *      npm run production:test
 *
 * The acceptance project does NOT depend on auth-setup.  If the storageState
 * file is missing, the first test will fail with a clear instruction to run
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
    // NO dependency on auth-setup.  The acceptance spec itself checks
    // whether .auth/production-state.json exists and fails with a clear
    // instruction if it does not.
    {
      name: "production-acceptance",
      testMatch: /acceptance\.spec\.ts/,
      use: {
        ...devices["Desktop Chrome"],
        channel: "chrome",
        viewport: { width: 1440, height: 900 },
        storageState: ".auth/production-state.json",
      },
    },
  ],
});
