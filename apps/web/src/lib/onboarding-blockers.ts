/**
 * Turning "activation is blocked" into something an operator can press.
 *
 * The onboarding page used to render each blocker as a bare `<li>` of text.
 * "Review 3 business details needing confirmation" told the operator what was
 * wrong and nothing about where to fix it — and the answer was a different page
 * (Settings → Governance & Approvals), so the only way through was hunting.
 *
 * The backend now sends each blocker with its destination. This module turns
 * that into a single ordered worklist: what is standing in the way, in the
 * order it should be dealt with, each one a link to the exact control.
 */

import type {
  BlockerResolution,
  OnboardingBlocker,
  OnboardingState,
  OnboardingStepKey,
} from "./platform-admin";

/**
 * The order the operator should work in.
 *
 * This is the real dependency order of setting a client up, not the order the
 * steps happen to be evaluated in: you need the client's identity before its
 * locations, a location before the site that attaches to one, and the business
 * details confirmed last because they are proposed *from* everything above.
 */
const CONTROL_ORDER: readonly string[] = [
  "organization-profile",
  "locations",
  "location-profile",
  "website-domain",
  "industry",
  "users",
  "products",
  "services",
  "approval-policy",
  "business-facts",
  "configuration",
  "runtime-controls",
  "connections",
  "activate",
];

function orderOf(control: string): number {
  const index = CONTROL_ORDER.indexOf(control);
  // An unrecognised control sorts last rather than first, so a blocker we did
  // not anticipate never displaces the ones we understand.
  return index === -1 ? CONTROL_ORDER.length : index;
}

/**
 * Where a blocker sends the operator, as a URL.
 *
 * Same-page blockers keep the current organization in the query string, because
 * the onboarding page selects its client from `?org=`; losing it would dump the
 * operator on a different client's setup.
 */
export function blockerHref(
  resolution: BlockerResolution,
  organizationId: string | null,
): string {
  const params = new URLSearchParams();
  if (organizationId) params.set("org", organizationId);
  const query = params.toString();
  return `${resolution.route}${query ? `?${query}` : ""}#${resolution.control}`;
}

/** True when following this blocker stays on the page the operator is already on. */
export function isSamePage(
  resolution: BlockerResolution,
  currentRoute: string,
): boolean {
  return resolution.route === currentRoute;
}

/**
 * The blockers, ordered, with their destinations.
 *
 * Falls back to the legacy string list when `blocker_details` is absent, which
 * happens only while a newer frontend is live against an API that has not
 * finished deploying. The fallback keeps the sentence and sends the operator to
 * the blockers panel rather than pretending to know where to go.
 */
export function resolveBlockers(
  state: Pick<OnboardingState, "blockers" | "blocker_details">,
): OnboardingBlocker[] {
  const detailed = state.blocker_details;
  const blockers: OnboardingBlocker[] =
    detailed && detailed.length > 0
      ? [...detailed]
      : state.blockers.map((message) => ({
          message,
          product_name: null,
          resolution: {
            step_key: null,
            route: "/onboarding",
            control: "blockers",
            permission: null,
            label: message.replace(/\.$/, ""),
          },
        }));

  return blockers.sort(
    (left, right) =>
      orderOf(left.resolution.control) - orderOf(right.resolution.control),
  );
}

/**
 * The sentence to show, with the product prefix folded in.
 *
 * The backend used to bracket the product name into the message itself
 * (`[Google Business Profile] Confirm 3 business details.`), which read like a
 * log line. The name is now a separate field, so the UI can present it as
 * provenance rather than punctuation.
 */
export function blockerText(blocker: OnboardingBlocker): string {
  return blocker.message;
}

/** Short imperative for the action control — "Confirm the business details". */
export function blockerActionLabel(blocker: OnboardingBlocker): string {
  return blocker.resolution.label;
}

/**
 * The step a blocker belongs to, for highlighting it in the stepper.
 */
export function blockerStepKey(
  blocker: OnboardingBlocker,
): OnboardingStepKey | null {
  return blocker.resolution.step_key;
}

/**
 * Scroll to and focus the control a blocker names.
 *
 * Focus matters as much as scroll: a sighted operator sees the section move,
 * but a keyboard or screen-reader user needs the caret to land there too.
 * Sections are not natively focusable, so this sets `tabindex="-1"` on arrival
 * and removes it on blur to avoid leaving a stray tab stop behind.
 */
export function focusControl(
  document: Document,
  control: string,
  options: { smooth?: boolean } = {},
): boolean {
  const target =
    document.getElementById(control) ??
    document.querySelector<HTMLElement>(`[data-control="${control}"]`);
  if (!target) return false;

  target.scrollIntoView({
    behavior: options.smooth === false ? "auto" : "smooth",
    block: "start",
  });

  if (!target.hasAttribute("tabindex")) {
    target.setAttribute("tabindex", "-1");
    target.addEventListener("blur", () => target.removeAttribute("tabindex"), {
      once: true,
    });
  }
  target.focus({ preventScroll: true });
  return true;
}

/**
 * Read the control named by the URL fragment on arrival, if any.
 *
 * Cross-page blockers navigate with a `#control` fragment. The browser cannot
 * scroll to it natively because the onboarding page renders its sections after
 * hydration, so the page re-applies it once the data is in.
 */
export function pendingControlFromHash(hash: string): string | null {
  const control = hash.replace(/^#/, "").trim();
  return control.length > 0 ? control : null;
}
