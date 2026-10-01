import { defineConfig } from "@playwright/test";
import base from "./playwright.config";
// Keep the same scenarios compatible with the default CI upstream on 4455.
process.env.CONSOLE_TEST_UPSTREAM_PORT = "4456";
export default defineConfig({
  ...base,
  testMatch: "phase6.spec.ts",
  use: { ...base.use, baseURL: "http://127.0.0.1:4347" },
  webServer: [
    {
      command: "node tests/browser/upstream.mjs",
      url: "http://127.0.0.1:4456/health",
      reuseExistingServer: false,
      env: { CONSOLE_TEST_UPSTREAM_PORT: "4456" },
    },
    {
      command: "npm run dev -- --port 4347 --ignore-lock",
      url: "http://127.0.0.1:4347/login/",
      reuseExistingServer: false,
      env: {
        ASTRO_DEV_BACKGROUND: "1",
        CONSOLE_ENV: "local",
        CONSOLE_ORIGIN: "http://127.0.0.1:4347",
        CONSOLE_EXPECTED_HOST: "127.0.0.1:4347",
        CONSOLE_API_ORIGIN: "http://127.0.0.1:4456",
        CONSOLE_SUPABASE_URL: "http://127.0.0.1:4456",
        CONSOLE_SUPABASE_KEY: "synthetic-key",
        CONSOLE_CSRF_SECRET: "synthetic-csrf-secret-32-characters-minimum",
      },
    },
  ],
});
