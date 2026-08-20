/**
 * Production auth bootstrap — manual, one-time, headed.
 *
 * Opens Chrome so the operator can log in manually, select Wheyland Electric,
 * and confirm the workspace is loaded.  Saves the resulting storageState
 * (cookies and localStorage) to a gitignored file so subsequent acceptance
 * runs can reuse the authenticated session.
 *
 * Note: Playwright `storageState` persists cookies and localStorage.
 * It does NOT persist sessionStorage, which is ephemeral by design.
 *
 * Usage:
 *   npm run production:auth
 *
 * The operator must:
 *   1. Enter credentials on the Supabase login form
 *   2. Complete MFA if prompted
 *   3. Wait for the workspace to load
 *   4. Use the organization switcher to select Wheyland Electric
 *   5. Confirm "Wheyland" appears in the topbar
 *   6. Close the browser tab (or the script will time out after 5 minutes)
 *
 * StorageState is saved ONLY when Wheyland Electric is confirmed in the
 * topbar.  If another organization is selected when the timeout expires,
 * the script fails and does NOT overwrite any existing auth state.
 */

import { test as setup } from "@playwright/test";
import { fileURLToPath } from "url";
import * as path from "path";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const AUTH_FILE = path.resolve(__dirname, "../../.auth/production-state.json");

setup("bootstrap production auth state", async ({ page }) => {
  // ── Phase 1: Navigate to login ──────────────────────────────────────
  await page.goto("/login");

  // ── Phase 2: Wait for operator to log in ─────────────────────────────
  console.log("");
  console.log("═══════════════════════════════════════════════════════");
  console.log("  PRODUCTION AUTH BOOTSTRAP");
  console.log("");
  console.log("  1. Log in with your Supabase credentials");
  console.log("  2. Complete MFA if prompted");
  console.log("  3. Wait for the workspace to load");
  console.log("");
  console.log("  Timeout: 5 minutes");
  console.log("═══════════════════════════════════════════════════════");
  console.log("");

  // Wait for the workspace shell to boot — any org is acceptable at
  // this stage; the operator hasn't had a chance to switch yet.
  await page.waitForFunction(
    () => {
      const el = document.querySelector("#active-organization-name");
      return (
        el && el.textContent !== "Loading…" && el.textContent!.trim().length > 0
      );
    },
    { timeout: 300_000 },
  );

  // Read the current org name for the operator
  const initialOrg =
    (await page.locator("#active-organization-name").textContent())?.trim() ??
    "";

  // ── Phase 3: Wait for operator to select Wheyland Electric ────────────
  const orgSwitcher = page.locator("#organization-switcher");
  const switcherVisible = await orgSwitcher.isVisible().catch(() => false);

  if (!switcherVisible && initialOrg.toLowerCase().includes("wheyland")) {
    // Wheyland is already selected and there's only one org (no switcher)
    console.log(`  ✓ Wheyland Electric already selected ("${initialOrg}")`);
  } else {
    // Need the operator to switch
    console.log("");
    console.log("═══════════════════════════════════════════════════════");
    console.log("  CURRENT ORGANIZATION:");
    console.log(`  "${initialOrg}"`);
    console.log("");
    if (switcherVisible) {
      console.log("  Use the organization switcher dropdown in the topbar");
      console.log("  to select Wheyland Electric.");
    } else {
      console.log("  No organization switcher is visible. You may need to");
      console.log("  log in with a different account or refresh the session.");
    }
    console.log("");
    console.log("  The script will wait up to 4 additional minutes for you");
    console.log('  to select "Wheyland Electric".');
    console.log("═══════════════════════════════════════════════════════");
    console.log("");

    // Poll for Wheyland in the topbar name
    try {
      await page.waitForFunction(
        () => {
          const el = document.querySelector("#active-organization-name");
          return (
            el &&
            el.textContent !== "Loading…" &&
            el.textContent!.trim().toLowerCase().includes("wheyland")
          );
        },
        { timeout: 240_000 }, // 4 additional minutes
      );
    } catch {
      const currentOrg =
        (await page
          .locator("#active-organization-name")
          .textContent()
          .catch(() => "unknown")) ?? "unknown";
      throw new Error(
        [
          "",
          "═══════════════════════════════════════════════════════",
          "  WHEYLAND ELECTRIC NOT SELECTED",
          "",
          `  Current organization: "${currentOrg}"`,
          "",
          "  Auth state was NOT saved because Wheyland Electric",
          "  was not selected within the timeout period.",
          "",
          "  Re-run `npm run production:auth` and select",
          "  Wheyland Electric using the organization switcher",
          "  in the topbar.",
          "═══════════════════════════════════════════════════════",
          "",
        ].join("\n"),
      );
    }
  }

  // ── Phase 4: Confirm and save ────────────────────────────────────────
  const confirmedOrg =
    (await page.locator("#active-organization-name").textContent())?.trim() ??
    "";

  if (!confirmedOrg.toLowerCase().includes("wheyland")) {
    throw new Error(
      `StorageState NOT saved — "${confirmedOrg}" is not Wheyland Electric.`,
    );
  }

  console.log("");
  console.log("═══════════════════════════════════════════════════════");
  console.log(`  CONFIRMED: "${confirmedOrg}"`);
  console.log("  Saving production auth state…");
  console.log("═══════════════════════════════════════════════════════");
  console.log("");

  await page.context().storageState({ path: AUTH_FILE });
  console.log(`Auth state saved to ${AUTH_FILE}`);
});
