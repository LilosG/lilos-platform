/**
 * Production auth bootstrap — manual, one-time, headed.
 *
 * Opens Chrome so the operator can log in manually and select the organization
 * explicitly approved for production acceptance. Saves the resulting
 * storageState (cookies and localStorage) to a gitignored file so subsequent
 * acceptance runs can reuse the authenticated session.
 *
 * The target organization is supplied at runtime; no client name belongs in
 * the acceptance harness source code.
 *
 * Usage:
 *   LILOS_PRODUCTION_ACCEPTANCE_ORG_NAME="<organization>" npm run production:auth
 *
 * Note: Playwright `storageState` persists cookies and localStorage.
 * It does NOT persist sessionStorage, which is ephemeral by design.
 */

import { test as setup } from "@playwright/test";
import { fileURLToPath } from "url";
import * as path from "path";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const AUTH_FILE = path.resolve(__dirname, "../../.auth/production-state.json");
const TARGET_ORG_NAME =
  process.env.LILOS_PRODUCTION_ACCEPTANCE_ORG_NAME?.trim() ?? "";

function normalizeOrganizationName(value: string): string {
  return value.trim().replace(/\s+/g, " ").toLowerCase();
}

setup("bootstrap production auth state", async ({ page }) => {
  if (!TARGET_ORG_NAME) {
    throw new Error(
      [
        "",
        "═══════════════════════════════════════════════════════",
        "  PRODUCTION ACCEPTANCE ORGANIZATION REQUIRED",
        "",
        "  Set LILOS_PRODUCTION_ACCEPTANCE_ORG_NAME to the",
        "  organization explicitly approved for production acceptance.",
        "",
        "  Example:",
        '    LILOS_PRODUCTION_ACCEPTANCE_ORG_NAME="<organization>" npm run production:auth',
        "═══════════════════════════════════════════════════════",
        "",
      ].join("\n"),
    );
  }

  await page.goto("/login");

  console.log("");
  console.log("═══════════════════════════════════════════════════════");
  console.log("  PRODUCTION AUTH BOOTSTRAP");
  console.log("");
  console.log(`  Target organization: "${TARGET_ORG_NAME}"`);
  console.log("");
  console.log("  1. Log in with your Supabase credentials");
  console.log("  2. Complete MFA if prompted");
  console.log("  3. Wait for the workspace to load");
  console.log(`  4. Select "${TARGET_ORG_NAME}" if it is not active`);
  console.log("");
  console.log("  Timeout: 5 minutes");
  console.log("═══════════════════════════════════════════════════════");
  console.log("");

  await page.waitForFunction(
    () => {
      const el = document.querySelector("#active-organization-name");
      const name = el?.textContent?.trim() ?? "";
      return name.length > 0 && name !== "Loading…";
    },
    undefined,
    { timeout: 300_000 },
  );

  const initialOrg =
    (await page.locator("#active-organization-name").textContent())?.trim() ??
    "";

  if (
    normalizeOrganizationName(initialOrg) !==
    normalizeOrganizationName(TARGET_ORG_NAME)
  ) {
    const orgSwitcher = page.locator("#organization-switcher");
    const switcherVisible = await orgSwitcher.isVisible().catch(() => false);

    if (!switcherVisible) {
      throw new Error(
        [
          "",
          "═══════════════════════════════════════════════════════",
          "  TARGET ORGANIZATION NOT AVAILABLE",
          "",
          `  Current organization: "${initialOrg}"`,
          `  Required organization: "${TARGET_ORG_NAME}"`,
          "",
          "  No organization switcher is visible. Auth state was NOT saved.",
          "═══════════════════════════════════════════════════════",
          "",
        ].join("\n"),
      );
    }

    console.log("");
    console.log(`  Current organization: "${initialOrg}"`);
    console.log(`  Select "${TARGET_ORG_NAME}" in the organization switcher.`);
    console.log("");

    try {
      await page.waitForFunction(
        (targetOrg) => {
          const el = document.querySelector("#active-organization-name");
          const current = (el?.textContent ?? "")
            .trim()
            .replace(/\s+/g, " ")
            .toLowerCase();
          const target = String(targetOrg)
            .trim()
            .replace(/\s+/g, " ")
            .toLowerCase();
          return current === target;
        },
        TARGET_ORG_NAME,
        { timeout: 240_000 },
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
          "  TARGET ORGANIZATION NOT SELECTED",
          "",
          `  Current organization: "${currentOrg}"`,
          `  Required organization: "${TARGET_ORG_NAME}"`,
          "",
          "  Auth state was NOT saved.",
          "═══════════════════════════════════════════════════════",
          "",
        ].join("\n"),
      );
    }
  }

  const confirmedOrg =
    (await page.locator("#active-organization-name").textContent())?.trim() ??
    "";

  if (
    normalizeOrganizationName(confirmedOrg) !==
    normalizeOrganizationName(TARGET_ORG_NAME)
  ) {
    throw new Error(
      `StorageState NOT saved — "${confirmedOrg}" does not match "${TARGET_ORG_NAME}".`,
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
