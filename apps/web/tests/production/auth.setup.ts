/**
 * Production auth bootstrap — manual, one-time, headed.
 *
 * Opens Chrome so the operator can log in manually. The target organization
 * is verified through authenticated production APIs, then the resulting
 * storageState (cookies and localStorage) is saved to a gitignored file for
 * subsequent acceptance runs.
 *
 * The target organization is supplied at runtime; no client name belongs in
 * the acceptance harness source code and the target does not need to be a
 * topbar membership for a platform administrator.
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
const API_BASE = "https://lilos-api.onrender.com";
const TARGET_ORG_NAME =
  process.env.LILOS_PRODUCTION_ACCEPTANCE_ORG_NAME?.trim() ?? "";

type ApiResult<T = unknown> = {
  status: number;
  data?: T;
  body?: string;
};

type TargetOrganization = {
  id: string;
  name: string;
  source: "platform" | "membership";
};

function normalizeOrganizationName(value: string): string {
  return value.trim().replace(/\s+/g, " ").toLowerCase();
}

async function authenticatedGet<T>(
  page: import("@playwright/test").Page,
  requestPath: string,
): Promise<ApiResult<T>> {
  return page.evaluate(
    async ({ apiBase, path }) => {
      const authKey = Object.keys(localStorage).find(
        (key) => key.startsWith("sb-") && key.endsWith("-auth-token"),
      );
      let token = "";
      if (authKey) {
        try {
          const session = JSON.parse(localStorage.getItem(authKey) ?? "{}");
          token = session?.access_token ?? "";
        } catch {
          token = "";
        }
      }

      const headers: Record<string, string> = { Accept: "application/json" };
      if (token) headers.Authorization = `Bearer ${token}`;

      let response: Response;
      try {
        response = await fetch(`${apiBase}${path}`, { headers });
      } catch (error) {
        return {
          status: 0,
          body: `Network error: ${String(error)}`,
        };
      }

      let responseBody: unknown;
      try {
        responseBody = await response.json();
      } catch {
        responseBody = await response.text().catch(() => "(unreadable)");
      }

      if (!response.ok) {
        const body =
          typeof responseBody === "string"
            ? responseBody
            : JSON.stringify(responseBody);
        return { status: response.status, body: body.slice(0, 500) };
      }

      return { status: response.status, data: responseBody };
    },
    { apiBase: API_BASE, path: requestPath },
  ) as Promise<ApiResult<T>>;
}

async function resolveTargetOrganization(
  page: import("@playwright/test").Page,
  targetName: string,
): Promise<TargetOrganization> {
  const target = normalizeOrganizationName(targetName);
  const platformMatches: Array<{ id: string; name: string }> = [];
  let platformAvailable = true;
  let offset = 0;

  for (let pageNumber = 0; pageNumber < 100; pageNumber += 1) {
    const result = await authenticatedGet<{
      data?: {
        items?: Array<{ id: string; name: string }>;
        has_more?: boolean;
        next_offset?: number | null;
      };
    }>(page, `/api/v1/platform/organizations?limit=100&offset=${offset}`);

    if (result.status === 403) {
      platformAvailable = false;
      break;
    }
    if (result.status !== 200) {
      throw new Error(
        `Platform organization lookup failed: HTTP ${result.status} — ${result.body ?? "no response body"}`,
      );
    }

    const payload = result.data?.data;
    for (const organization of payload?.items ?? []) {
      if (normalizeOrganizationName(organization.name) === target) {
        platformMatches.push(organization);
      }
    }

    if (!payload?.has_more) break;
    const nextOffset = payload.next_offset;
    if (typeof nextOffset !== "number" || nextOffset <= offset) {
      throw new Error(
        "Platform organization pagination returned an invalid next_offset.",
      );
    }
    offset = nextOffset;
  }

  if (platformAvailable) {
    if (platformMatches.length === 1) {
      return { ...platformMatches[0], source: "platform" };
    }
    if (platformMatches.length > 1) {
      throw new Error(
        `Target organization "${targetName}" is ambiguous in platform administration.`,
      );
    }
    throw new Error(
      `Target organization "${targetName}" was not found in platform administration.`,
    );
  }

  const memberships = await authenticatedGet<{
    data?: Array<{
      id: string;
      organization_id: string;
      organization_name: string;
    }>;
  }>(page, "/api/v1/me/organizations");
  if (memberships.status !== 200) {
    throw new Error(
      `Membership organization lookup failed: HTTP ${memberships.status} — ${memberships.body ?? "no response body"}`,
    );
  }

  const membershipMatches = (memberships.data?.data ?? []).filter(
    (organization) =>
      normalizeOrganizationName(organization.organization_name ?? "") ===
      target,
  );
  if (membershipMatches.length !== 1) {
    throw new Error(
      `Target organization "${targetName}" must resolve to exactly one accessible organization; found ${membershipMatches.length}.`,
    );
  }

  const organization = membershipMatches[0];
  return {
    id: organization.organization_id ?? organization.id,
    name: organization.organization_name,
    source: "membership",
  };
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
  console.log(`  Acceptance target: "${TARGET_ORG_NAME}"`);
  console.log("");
  console.log("  1. Log in with your Supabase credentials");
  console.log("  2. Complete MFA if prompted");
  console.log("  3. Wait for the agency workspace to load");
  console.log("  4. No client workspace switching is required");
  console.log("");
  console.log("  Timeout: 5 minutes");
  console.log("═══════════════════════════════════════════════════════");
  console.log("");

  await page.locator("#sign-out-button").waitFor({
    state: "visible",
    timeout: 300_000,
  });
  await page.locator("#workspace-navigation").waitFor({
    state: "visible",
    timeout: 20_000,
  });

  const operatorWorkspace =
    (await page.locator("#active-organization-name").textContent())?.trim() ??
    "unknown";
  const target = await resolveTargetOrganization(page, TARGET_ORG_NAME);

  console.log("");
  console.log("═══════════════════════════════════════════════════════");
  console.log(`  Authenticated workspace: "${operatorWorkspace}"`);
  console.log(`  Verified acceptance target: "${target.name}"`);
  console.log(`  Resolution path: ${target.source}`);
  console.log("  Saving production auth state…");
  console.log("═══════════════════════════════════════════════════════");
  console.log("");

  await page.context().storageState({ path: AUTH_FILE });
  console.log(`Auth state saved to ${AUTH_FILE}`);
});