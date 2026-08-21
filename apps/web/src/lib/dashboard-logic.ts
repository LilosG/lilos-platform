import type { ApiOutcome } from "./api-client";
import type { MyOrganization, ProductReadiness } from "./workspace";

function availableLocalStorage(): Storage | null {
  if (typeof window === "undefined") return null;

  try {
    const storage = window.localStorage;
    return storage && typeof storage.getItem === "function" ? storage : null;
  } catch {
    return null;
  }
}

/** Prefers an active membership; falls back to the first membership so a paused
 * or invited-only org is still visible rather than silently hidden. */
export function selectDefaultOrganization(
  organizations: readonly MyOrganization[],
): MyOrganization | null {
  if (!organizations.length) return null;

  const storage = availableLocalStorage();

  if (typeof window !== "undefined") {
    const urlOrgId = new URLSearchParams(window.location.search).get("org");
    const storedOrgId = storage?.getItem("selected_org_id") ?? null;
    const targetId = urlOrgId || storedOrgId;

    if (targetId) {
      const matched = organizations.find(
        (item) => item.organization_id === targetId,
      );
      if (matched) {
        storage?.setItem("selected_org_id", matched.organization_id);
        return matched;
      }
    }
  }

  const defaultOrg =
    organizations.find((item) => item.membership_status === "active") ??
    organizations[0] ??
    null;

  if (defaultOrg) {
    storage?.setItem("selected_org_id", defaultOrg.organization_id);
  }

  return defaultOrg;
}

export type ReadinessSummary = {
  status: "ready" | "blocked" | "setup" | "missing";
  detail: string;
};

/** Converts a readiness API outcome into a truthful display summary. Every
 * non-"ok" outcome maps to "missing" with a specific, non-fabricated reason —
 * never a guessed ready/blocked state. */
export function summarizeReadiness(
  outcome: ApiOutcome<ProductReadiness>,
): ReadinessSummary {
  switch (outcome.kind) {
    case "ok": {
      const state = outcome.data.readiness_state;
      const status = state === "not_entitled" ? "setup" : state;
      const blocking = outcome.data.blocking_requirements[0];
      return { status, detail: blocking ? blocking.remediation : "Ready." };
    }
    case "forbidden":
      return {
        status: "missing",
        detail: "You do not have permission to view this product.",
      };
    case "not-found":
      return {
        status: "missing",
        detail: "Not available for this organization.",
      };
    case "unauthenticated":
      return {
        status: "missing",
        detail: "Your session has expired. Sign in again.",
      };
    case "disconnected":
      return { status: "missing", detail: "Could not reach the platform API." };
    case "not-configured":
      return {
        status: "missing",
        detail: "This deployment is not configured.",
      };
    case "error":
      return { status: "missing", detail: outcome.message };
  }
}
