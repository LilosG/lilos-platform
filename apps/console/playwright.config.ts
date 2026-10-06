import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./tests/browser",
  workers: 1,
  fullyParallel: false,
  use: {
    baseURL: "http://127.0.0.1:4346",
    trace: "retain-on-failure",
    // Cloud sessions ship a preinstalled Chromium; CI leaves this unset.
    launchOptions: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE
      ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE }
      : {},
  },
  projects: [
    { name: "desktop", use: { viewport: { width: 1440, height: 1000 } } },
    { name: "mobile", use: { viewport: { width: 390, height: 844 } } },
  ],
  webServer: [
    {
      command: "node tests/browser/upstream.mjs",
      url: "http://127.0.0.1:4455/health",
      reuseExistingServer: false,
    },
    {
      command: "npm run dev -- --port 4346 --ignore-lock",
      url: "http://127.0.0.1:4346/login/",
      reuseExistingServer: false,
      env: {
        ASTRO_DEV_BACKGROUND: "1",
        CONSOLE_ENV: "local",
        CONSOLE_ORIGIN: "http://127.0.0.1:4346",
        CONSOLE_EXPECTED_HOST: "127.0.0.1:4346",
        CONSOLE_API_ORIGIN: "http://127.0.0.1:4455",
        CONSOLE_SUPABASE_URL: "http://127.0.0.1:4455",
        CONSOLE_SUPABASE_KEY: "synthetic-key",
        CONSOLE_CSRF_SECRET: "synthetic-csrf-secret-32-characters-minimum",
      },
    },
  ],
});
