/**
 * Owns both local-only processes required by Packet 4 visual regression.
 * Playwright launches this file only when LILOS_PACKET4_FIXTURES=1 is set.
 */
import process from "node:process";
import { fileURLToPath, URL } from "node:url";

if (process.env.LILOS_PACKET4_FIXTURES !== "1") {
  throw new Error(
    "Packet 4 fixtures are disabled. Set LILOS_PACKET4_FIXTURES=1 for local visual regression only.",
  );
}

process.env.PUBLIC_LILOS_API_BASE_URL = "http://127.0.0.1:4322";
process.env.PUBLIC_LILOS_SUPABASE_URL = "http://127.0.0.1:4322";
process.env.PUBLIC_LILOS_SUPABASE_ANON_KEY = "packet-4-fixture";

const { dev } = await import("astro");
await dev({
  root: fileURLToPath(new URL("../../../", import.meta.url)),
  server: { host: "127.0.0.1", port: 4321 },
});

await import("./evidence-server.mjs");
