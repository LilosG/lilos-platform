import { defineConfig } from "astro/config";
import vercel from "@astrojs/vercel";
import tailwindcss from "@tailwindcss/vite";
import { execFileSync } from "node:child_process";
// Use the merged Phase 0.5 check, rather than a second staging policy.
if (
  process.env.CONSOLE_ENV === "staging" ||
  process.env.VERCEL_ENV === "preview"
) {
  execFileSync("uv", ["run", "python", "scripts/validate_staging_console.py"], {
    cwd: new URL("../../", import.meta.url),
    stdio: "inherit",
  });
}
export default defineConfig({
  output: "server",
  adapter: vercel(),
  trailingSlash: "always",
  devToolbar: { enabled: false },
  vite: { plugins: [tailwindcss()] },
});
