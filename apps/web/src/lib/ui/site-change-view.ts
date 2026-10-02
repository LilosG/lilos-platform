import type { SEORecommendation } from "../seo";

/**
 * The operator's view of an approved SEO site change, derived from typed values only.
 *
 * Every state here comes from a closed code or enum the API sends (`blocked_code`,
 * `build_state`, `verification_state`, ...). Nothing is inferred from English text
 * (CLAUDE.md: typed contracts, never matching sentences in the frontend), and a value
 * the API did not send is shown as not-yet-known rather than as progress.
 */

export type StageTone = "ready" | "pending" | "blocked" | "neutral";

export type SiteChangeStage = {
  label: string;
  tone: StageTone;
  text: string;
};

export type SiteChangeView = {
  changes: {
    label: string;
    before: string;
    after: string;
    rationale: string;
  }[];
  stages: SiteChangeStage[];
  pullRequest: { href: string; label: string } | null;
  blocked: { code: string; message: string } | null;
  liveChecks: {
    label: string;
    expected: string;
    observed: string;
    matches: boolean;
  }[];
};

const FIELD_LABELS: Record<string, string> = {
  seo_title: "SEO title",
  meta_description: "Meta description",
  h1: "Main heading (H1)",
  body_section: "Body section",
  schema: "Structured data",
  internal_link: "Internal link",
};

/**
 * Operator copy for every typed code a site change can stop on. Mirrors
 * apps/api/app/products/seo/site_change_codes.py::SiteChangeCode; a code missing
 * here still renders (with the code itself), so a new backend code cannot blank a message.
 */
const BLOCKED_COPY: Record<string, string> = {
  SITE_MAPPING_REQUIRED:
    "This page has no confirmed file and field mapping, so LILOs cannot edit it safely. Add a page map for this site in Integrations.",
  SITE_CHANGE_FINGERPRINT_MISMATCH:
    "The change no longer matches what was approved. Nothing was written; create a new recommendation.",
  CHANGE_SET_INVALID:
    "The approved change could not be read. Nothing was written; create a new recommendation.",
  CHECKS_UNAVAILABLE:
    "The site has no build checks and no Vercel preview to prove the change builds, so the pull request was not merged. Review and merge it yourself, or add a check.",
  CONTENT_CHECKS_FAILED:
    "The site's build checks failed on the pull request, so it was not merged.",
  CONTENT_DEPLOYMENT_FAILED:
    "The change merged but the production deployment failed.",
  SITE_CHANGE_VERIFICATION_FAILED:
    "The change deployed, but the live page does not show the approved values. See the observed values below.",
  GITHUB_CONNECTION_REQUIRED:
    "GitHub is not connected for this website. Connect it in Integrations.",
  GITHUB_CREDENTIAL_REQUIRED:
    "The GitHub credential is unavailable. Reconnect GitHub in Integrations.",
  PUBLISHING_TARGET_NOT_CONFIGURED:
    "No active GitHub publishing target is configured for this website.",
  PROVIDER_WRITES_DISABLED:
    "Provider writes are disabled in this environment, so nothing was sent to GitHub.",
  CONTENT_PR_CLOSED: "The pull request was closed without merging.",
  CONTENT_PR_HEAD_CHANGED:
    "The pull request was changed after approval, so it was not merged.",
  GITHUB_APP_PERMISSION_MISSING:
    "GitHub refused a read this change needs: the LILOs GitHub App lacks the Checks or Commit statuses permission. Grant it on the app; the change resumes from its pull request.",
  CONTENT_DEPLOYMENT_RATE_LIMITED:
    "The change merged, but the host refused to build it because its build limit was reached. It deploys once the limit clears or when it is redeployed.",
};

const BUILD_GATE_LABELS: Record<string, string> = {
  repository_ci: "Site checks",
  vercel_preview: "Vercel preview",
  none: "No checks found",
};

function fieldLabel(field: string): string {
  return FIELD_LABELS[field] ?? field;
}

export function describeBlockedCode(code: string): string {
  return (
    BLOCKED_COPY[code] ?? "The change stopped. No further detail was recorded."
  );
}

function buildStage(
  state: NonNullable<SEORecommendation["site_change"]>,
): SiteChangeStage {
  const gate = state.build_gate
    ? (BUILD_GATE_LABELS[state.build_gate] ?? state.build_gate)
    : null;
  switch (state.build_state) {
    case "passed":
      return {
        label: "Build",
        tone: "ready",
        text: `${gate ?? "Checks"} passed`,
      };
    case "failed":
      return {
        label: "Build",
        tone: "blocked",
        text: `${gate ?? "Checks"} failed`,
      };
    case "pending":
      return {
        label: "Build",
        tone: "pending",
        text: `Waiting on ${gate ?? "checks"}`,
      };
    case "unavailable":
      return {
        label: "Build",
        tone: "blocked",
        text: "No checks to gate the merge",
      };
    default:
      return { label: "Build", tone: "neutral", text: "Not started" };
  }
}

function verificationStage(
  state: NonNullable<SEORecommendation["site_change"]>,
): SiteChangeStage {
  switch (state.verification_state) {
    case "verified":
      return {
        label: "Live check",
        tone: "ready",
        text: "Live page shows the change",
      };
    case "failed":
      return {
        label: "Live check",
        tone: "blocked",
        text: "Live page differs",
      };
    case "pending":
      return {
        label: "Live check",
        tone: "pending",
        text: "Waiting for the deploy",
      };
    default:
      return { label: "Live check", tone: "neutral", text: "Not started" };
  }
}

/** The view for one recommendation, or null when it carries no site change at all. */
export function siteChangeView(
  recommendation: SEORecommendation | null | undefined,
): SiteChangeView | null {
  if (!recommendation) return null;
  const state = recommendation.site_change;
  const hasChanges = recommendation.change_set.length > 0;
  if (!state && !hasChanges && !recommendation.change_set_limitation_code) {
    return null;
  }

  const blockedCode =
    state?.blocked_code ?? recommendation.change_set_limitation_code;
  const mapping: SiteChangeStage =
    state?.mapping_state === "required" ||
    blockedCode === "SITE_MAPPING_REQUIRED"
      ? { label: "Mapping", tone: "blocked", text: "Page is not mapped" }
      : state?.mapping_state === "mapped" || hasChanges
        ? { label: "Mapping", tone: "ready", text: "Page mapped to its file" }
        : { label: "Mapping", tone: "neutral", text: "Not checked" };

  return {
    changes: recommendation.change_set.map((item) => ({
      label: fieldLabel(item.field),
      before: item.current_value,
      after: item.proposed_value,
      rationale: item.rationale,
    })),
    stages: state
      ? [mapping, buildStage(state), verificationStage(state)]
      : [mapping],
    pullRequest: state?.pull_request_url
      ? { href: state.pull_request_url, label: "View pull request on GitHub" }
      : null,
    blocked: blockedCode
      ? { code: blockedCode, message: describeBlockedCode(blockedCode) }
      : null,
    liveChecks: (state?.live_checks ?? [])
      .filter(
        (check) => check.state === "verified" || check.state === "mismatch",
      )
      .map((check) => ({
        label: fieldLabel(check.field),
        expected: check.expected,
        observed: check.observed ?? "Not observed",
        matches: check.state === "verified",
      })),
  };
}

/** Only a GitHub pull-request URL is ever rendered as a link. */
export function isSafePullRequestUrl(href: string): boolean {
  try {
    const url = new URL(href);
    return url.protocol === "https:" && url.hostname === "github.com";
  } catch {
    return false;
  }
}
