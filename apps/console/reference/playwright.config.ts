import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./tests/browser",
  fullyParallel: true,
  workers: 3,
  use: {
    baseURL: "http://127.0.0.1:4322",
    viewport: { width: 1440, height: 1000 },
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command: "npm run preview -- --port 4322 --ignore-lock",
      url: "http://127.0.0.1:4322",
      reuseExistingServer: !process.env.CI,
    },
    {
      command:
        "python3 -m http.server 8000 --bind 127.0.0.1 --directory reference/revision-10/dist",
      url: "http://127.0.0.1:8000",
      reuseExistingServer: !process.env.CI,
    },
  ],
});
