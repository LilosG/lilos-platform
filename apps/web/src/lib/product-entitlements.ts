/**
 * Shared, architecture-correct operator rendering for product entitlements.
 *
 * Both /onboarding (platform-administrator client-onboarding flow) and
 * /administration (operator product catalog) must render the *same* truthful
 * product-entitlement state and offer the *same* Enable/transition controls
 * — never two divergent implementations. The backend rule that an effective
 * entitlement is required before a GBP OAuth connection can begin lives in
 * `apps.api.app.routes.integrations._require_effective_entitlement` and is
 * NOT weakened here: this module only lets an operator create or transition
 * an entitlement through the existing production platform-administration
 * API.
 *
 * Lifecycle guards are owned by the backend (`ENTITLEMENT_TRANSITIONS`). A
 * transition the current status does not permit is rejected by the API with
 * `TRANSITION_NOT_ALLOWED`; this module never hides that or retries with a
 * different transition.
 */
import {
  createProductEntitlement,
  fetchProductEntitlements,
  transitionProductEntitlement,
  NOT_EFFECTIVE_ENTITLEMENT_STATUSES,
  SELECTED_ENTITLEMENT_STATUSES,
  type EntitlementStatus,
  type ProductEntitlement,
} from "./platform-admin";
import type { ApiOutcome } from "./api-client";
import { statusLabel } from "./status-language";

/**
 * Re-export the truthful entitlement-status sets so operator UIs consume one
 * shared definition (mirroring the backend
 * `NOT_EFFECTIVE_ENTITLEMENT_STATUSES` frozenset and the onboarding read
 * model's `_NOT_SELECTED_ENTITLEMENT_STATUSES` inverse). Both /onboarding
 * and /administration import these from here so the two pages cannot diverge
 * on which statuses count as effective / selected.
 */
export {
  NOT_EFFECTIVE_ENTITLEMENT_STATUSES,
  SELECTED_ENTITLEMENT_STATUSES,
  type EntitlementStatus,
  type ProductEntitlement,
};

/**
 * Stable audit source recorded on every entitlement created from the
 * operator onboarding/administration workflow. Operators act through the
 * platform-administration API (not the deprecated DB provisioning script),
 * so the audit row attributes the action to the authenticated platform
 * administrator with this stable source label.
 */
export const OPERATOR_ENTITLEMENT_SOURCE = "platform_admin_onboarding";

/**
 * The set of statuses from which an operator may legitimately restore the
 * entitlement to `setup_required` (re-enable). Derived from the backend
 * `ENTITLEMENT_TRANSITIONS` table:
 *
 *   not_enabled -> {setup_required, archived}
 *   suspended   -> {setup_required, archived}
 *   archived    -> {} (terminal)
 *
 * `archived` is intentionally absent: it is a terminal state and must not be
 * silently reactivated from the UI.
 */
export const RE_ENABLE_STATUSES: ReadonlySet<EntitlementStatus> =
  new Set<EntitlementStatus>(["not_enabled", "suspended"]);

export function isEffectiveEntitlement(status: EntitlementStatus): boolean {
  return !NOT_EFFECTIVE_ENTITLEMENT_STATUSES.has(status);
}

export function isSelectedEntitlement(status: EntitlementStatus): boolean {
  return SELECTED_ENTITLEMENT_STATUSES.has(status);
}

/**
 * Map an entitlement status to the readiness badge kind used across the
 * workspace (`status--ready`, `status--setup`, `status--blocked`,
 * `status--degraded`). Mirrors the truthful lifecycle state rather than
 * inventing a new badge vocabulary.
 */
export function entitlementBadgeKind(status: EntitlementStatus): string {
  if (status === "active" || status === "ready") return "ready";
  if (status === "paused" || status === "degraded") return "degraded";
  if (
    status === "not_enabled" ||
    status === "archived" ||
    status === "suspended"
  )
    return "blocked";
  return "setup";
}

/**
 * Human-readable label for an entitlement status, used in badges/aria. Kept
 * truthful to the backend value (no euphemisms like "active" for
 * `setup_required`).
 */
export function entitlementStatusLabel(status: EntitlementStatus): string {
  return statusLabel(status);
}

export type EntitlementRowState = {
  /** The product_key this row corresponds to (e.g. "gbp"). */
  productKey: string;
  /** Truthful entitlement row from the API, or `null` when none exists. */
  entitlement: ProductEntitlement | null;
  /**
   * `true` when no entitlement row exists and an Enable action is available.
   * `false` once one exists (even if not effective) — recreation is blocked
   * by the backend `ENTITLEMENT_CONFLICT` guard and must not be attempted.
   */
  canEnable: boolean;
  /**
   * `true` when the existing entitlement is in a status from which an
   * operator may legitimately restore to `setup_required`
   * (`not_enabled`/`suspended`). `archived` is terminal and never
   * re-enableable from the UI.
   */
  canReEnable: boolean;
  /** `true` when the entitlement is effective for the GBP OAuth gate. */
  effective: boolean;
  /** `true` when the onboarding read model would count it as selected. */
  selected: boolean;
};

/**
 * Build a truthful row-state descriptor from the entitlement row (if any)
 * for a single product. Used by both pages to decide which control (Enable
 * vs. Restore vs. none) to render, and to ensure the same rule is applied
 * everywhere.
 */
export function describeEntitlementRow(
  productKey: string,
  entitlement: ProductEntitlement | null,
): EntitlementRowState {
  if (entitlement === null) {
    return {
      productKey,
      entitlement: null,
      canEnable: true,
      canReEnable: false,
      effective: false,
      selected: false,
    };
  }
  return {
    productKey,
    entitlement,
    canEnable: false,
    canReEnable: RE_ENABLE_STATUSES.has(entitlement.status),
    effective: isEffectiveEntitlement(entitlement.status),
    selected: isSelectedEntitlement(entitlement.status),
  };
}

export type ProductEntitlementMap = Map<string, ProductEntitlement>;

/**
 * Fetch the truthful entitlement rows for an organization and index them by
 * `product_id`-free product key. Returns a map plus the raw outcome so a
 * caller can render a truthful failure (e.g. forbidden to a non-admin)
 * instead of a fabricated empty state.
 *
 * Note: entitlement rows carry `product_id`, not `product_key`. Callers pass
 * the catalog `product_id -> product_key` mapping (already loaded by both
 * pages via `fetchProducts`) so the result is keyed by the stable product
 * key the rest of the UI uses.
 */
export async function loadEntitlementsByKey(
  organizationId: string,
  productIdToKey: Map<string, string>,
): Promise<{
  outcome: ApiOutcome<ProductEntitlement[]>;
  byKey: ProductEntitlementMap;
}> {
  const outcome = await fetchProductEntitlements(organizationId);
  const byKey: ProductEntitlementMap = new Map();
  if (outcome.kind === "ok") {
    for (const row of Array.isArray(outcome.data) ? outcome.data : []) {
      const key = productIdToKey.get(row.product_id);
      if (key) byKey.set(key, row);
    }
  }
  return { outcome, byKey };
}

/**
 * Enable a product for an organization by creating an entitlement through
 * the production platform-administration API. The resulting
 * `setup_required` entitlement is effective enough to permit the GBP OAuth
 * connection. Resolves to the created row or a truthful failure outcome
 * (e.g. `ENTITLEMENT_CONFLICT` if one already exists — the caller must NOT
 * retry by recreating).
 */
export function enableProduct(
  organizationId: string,
  productKey: string,
  reason: string,
): Promise<ApiOutcome<ProductEntitlement>> {
  return createProductEntitlement(organizationId, {
    product_key: productKey,
    source: OPERATOR_ENTITLEMENT_SOURCE,
    reason,
  });
}

/**
 * Restore an existing non-effective (but non-terminal) entitlement to
 * `setup_required` through the production transition API. The backend
 * `ENTITLEMENT_TRANSITIONS` guard rejects this for terminal/unsupported
 * statuses (e.g. `archived`); callers must gate on `canReEnable` before
 * offering the control.
 */
export function reEnableProduct(
  organizationId: string,
  entitlement: ProductEntitlement,
  reason: string,
): Promise<ApiOutcome<ProductEntitlement>> {
  return transitionProductEntitlement(organizationId, entitlement.id, {
    target_status: "setup_required",
    reason,
    expected_version: entitlement.version,
  });
}
