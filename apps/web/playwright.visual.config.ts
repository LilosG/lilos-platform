import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/visual",
  outputDir: "./.playwright-visual-output",
  snapshotPathTemplate: "{testDir}/__snapshots__/{arg}{ext}",
  reporter: "line",
  retries: 0,
  expect: { timeout: 20_000 },
  use: {
    baseURL: "http://127.0.0.1:4322",
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 1,
    trace: "retain-on-failure",
  },
  webServer: {
    command:
      "LILOS_PACKET4_FIXTURES=1 node --experimental-strip-types tests/fixtures/packet-4/visual-server.mjs",
    url: "http://127.0.0.1:4322/ready",
    reuseExistingServer: false,
    timeout: 120_000,
  },
});
