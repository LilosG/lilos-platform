import type { ContentView, WebsiteView } from "../adapters/website-content";
import { fmt } from "./present";
import type { Chip } from "./status";
import { outline, wordCount } from "./markdown";

type Row = WebsiteView["content"][number];

// --- what a piece of content is, by typed key ---------------------------------------------

export const COMPOSE_TYPES = [
  { key: null, label: "Let Claude decide" },
  { key: "blog_post", label: "Blog post" },
  { key: "listicle", label: "Listicle" },
  { key: "landing_page", label: "Landing page" },
  { key: "service_page", label: "Service page" },
  { key: "location_page", label: "Location page" },
  { key: "guide", label: "Guide" },
] as const;
export type ComposeType = NonNullable<(typeof COMPOSE_TYPES)[number]["key"]>;
const typeLabels: Record<string, string> = {
  blog: "Blog post",
  blog_post: "Blog post",
  article: "Article",
  listicle: "Listicle",
  list_post: "Listicle",
  roundup: "Roundup",
  pillar: "Pillar page",
  guide: "Guide",
  local_guide: "Guide",
  page: "Page",
  landing: "Landing page",
  landing_page: "Landing page",
  service_page: "Service page",
  location_page: "Location page",
};
/** A content type for a person. A type this app does not know reads as plain "Content". */
export const typeLabel = (key: string): string =>
  typeLabels[key.replaceAll("-", "_")] ?? "Content";
const PAGE_TYPES = new Set([
  "page",
  "landing",
  "landing_page",
  "service_page",
  "location_page",
]);
/** Landing, service and location pages are shown apart from articles. */
export const isPageType = (key: string): boolean =>
  PAGE_TYPES.has(key.replaceAll("-", "_"));

// --- stage, revision and publication chips -------------------------------------------------

const stageChips: Record<string, Chip> = {
  writing: { label: "Writing", tone: "neutral" },
  compose_failed: { label: "Could not write", tone: "error" },
  brief_needed: { label: "Needs a brief", tone: "neutral" },
  draft_needed: { label: "Needs a draft", tone: "neutral" },
  drafting: { label: "Draft", tone: "neutral" },
  editorial_review: { label: "Ready for review", tone: "warn" },
  client_review: { label: "Awaiting final approval", tone: "warn" },
  revision_needed: { label: "Needs changes", tone: "warn" },
  ready_to_publish: { label: "Approved", tone: "" },
  publishing: { label: "Publishing", tone: "neutral" },
  published: { label: "Published", tone: "" },
  needs_attention: { label: "Needs attention", tone: "error" },
};
export const stageChip = (stage: string): Chip =>
  stageChips[stage] ?? { label: "In progress", tone: "neutral" };
const revisionChips: Record<string, Chip> = {
  draft: { label: "Draft", tone: "neutral" },
  validation_failed: { label: "Needs changes", tone: "warn" },
  awaiting_editorial: { label: "Awaiting review", tone: "warn" },
  awaiting_client: { label: "Awaiting final approval", tone: "warn" },
  approved: { label: "Approved", tone: "" },
  rejected: { label: "Rejected", tone: "error" },
  superseded: { label: "Replaced", tone: "neutral" },
  published: { label: "Published", tone: "" },
};
export const revisionChip = (status: string): Chip =>
  revisionChips[status] ?? { label: "Draft", tone: "neutral" };
const publicationChips: Record<string, Chip> = {
  reserved: { label: "Queued", tone: "neutral" },
  branch_created: { label: "Preparing", tone: "neutral" },
  pull_request_created: { label: "Checking", tone: "neutral" },
  checks_running: { label: "Checking", tone: "neutral" },
  checks_failed: { label: "Checks failed", tone: "error" },
  merged: { label: "Deploying", tone: "neutral" },
  deployment_pending: { label: "Deploying", tone: "neutral" },
  deployed: { label: "Deployed", tone: "" },
  verified: { label: "Live", tone: "" },
  failed: { label: "Failed", tone: "error" },
  reconciliation_required: { label: "Needs attention", tone: "error" },
  rolled_back: { label: "Rolled back", tone: "warn" },
};
export const publicationChip = (status: string): Chip =>
  publicationChips[status] ?? { label: "In progress", tone: "neutral" };

// --- why a piece could not be written, by typed code ---------------------------------------

export interface Failure {
  title: string;
  detail: string;
}
const failures: Record<string, Failure> = {
  CONTENT_WEBSITE_NOT_CRAWLED: {
    title: "This website has not been checked yet",
    detail:
      "Links in a draft must point to pages that really exist. Run a website check first, then try again.",
  },
  CONTENT_NO_APPROVED_FACTS: {
    title: "There are no approved business facts yet",
    detail:
      "Content is written from what the business has confirmed. Add or approve business facts, then try again.",
  },
  CONTENT_BELOW_QUALITY_FLOOR: {
    title: "The draft was not long or well linked enough",
    detail:
      "It missed the length, structure or internal-link standard even after one repair attempt, so it was not saved. Try again, or add detail to the prompt.",
  },
  CONTENT_PLAN_INVALID: {
    title: "The request could not be turned into a plan",
    detail:
      "Say a little more about the topic or pick a content type, then try again.",
  },
  AI_PROVIDER_CONFIGURATION_ERROR: {
    title: "Writing is not set up",
    detail: "The writing service is not configured. Contact support.",
  },
  AI_PROVIDER_TEMPORARY_FAILURE: {
    title: "The writing service is busy",
    detail: "Nothing was lost. Try again in a moment.",
  },
};
const fallbackFailure: Failure = {
  title: "The draft could not be written",
  detail: "Nothing was saved. Try again.",
};
export const failureFor = (code: string | null | undefined): Failure =>
  (code && failures[code]) || fallbackFailure;

// --- the list ------------------------------------------------------------------------------

export interface ContentRow {
  id: string;
  href: string;
  title: string;
  type: string;
  isPage: boolean;
  stage: Chip;
  writing: boolean;
  failed: boolean;
  failure: Failure | null;
  retryPrompt: string | null;
  words: string;
  revision: Chip | null;
  publication: Chip | null;
}
export function contentRows(items: readonly Row[], base: string): ContentRow[] {
  return items.map((item) => {
    const writing = item.compose?.status === "writing";
    const failed = item.compose?.status === "failed";
    return {
      id: item.id,
      href: `${base}content/${item.id}/`,
      title: item.title,
      type: typeLabel(item.content_type),
      isPage: isPageType(item.content_type),
      stage: stageChip(item.stage),
      writing,
      failed,
      failure: failed ? failureFor(item.compose?.failure_code) : null,
      retryPrompt: failed ? (item.compose?.prompt ?? null) : null,
      // A draft that does not exist has no length; it is never shown as 0.
      words: item.word_count == null ? "–" : fmt(item.word_count),
      revision: item.latest_revision_status
        ? revisionChip(item.latest_revision_status)
        : null,
      publication: item.publication_status
        ? publicationChip(item.publication_status)
        : null,
    };
  });
}
/** Any item still being written: the screen refreshes itself while this is true. */
export const anyWriting = (items: readonly Row[]): boolean =>
  items.some((item) => item.compose?.status === "writing");

// --- the draft review ----------------------------------------------------------------------

const checkLabels: Record<string, { pass: string; fail: string }> = {
  article_too_thin: { pass: "Meets length", fail: "Too short" },
  article_heading_depth_missing: {
    pass: "Enough sections",
    fail: "Too few sections",
  },
  article_sections_too_thin: {
    pass: "Sections have depth",
    fail: "Thin sections",
  },
  article_internal_links_missing: {
    pass: "Enough internal links",
    fail: "Too few internal links",
  },
  article_internal_link_unverified: {
    pass: "Every link verified",
    fail: "Unverified link",
  },
  article_anchor_generic: {
    pass: "Descriptive anchors",
    fail: "Generic anchor",
  },
  article_anchor_stuffing: {
    pass: "Anchors not repeated",
    fail: "Repeated anchor",
  },
  article_anchor_ambiguous: {
    pass: "Anchors are distinct",
    fail: "Same anchor, different pages",
  },
  article_commercial_link_missing: {
    pass: "Links to a service or menu page",
    fail: "No service or menu link",
  },
  article_faq_depth_missing: { pass: "Enough FAQs", fail: "Too few FAQs" },
  article_meta_description_missing: {
    pass: "Has a meta description",
    fail: "No meta description",
  },
  article_seo_title_missing: {
    pass: "Has a search title",
    fail: "No search title",
  },
  article_search_intent_headings_missing: {
    pass: "Headings match the topic",
    fail: "Headings drift from the topic",
  },
  article_repeated_paragraphs: {
    pass: "No repeated text",
    fail: "Repeated text",
  },
  article_duplicate_headings: {
    pass: "Unique headings",
    fail: "Duplicate headings",
  },
};
export interface QualityCheck {
  code: string;
  passed: boolean;
  chip: Chip;
}
export interface LinkRow {
  anchor: string;
  url: string;
  verified: boolean;
  chip: Chip;
}
export interface InboundEdit {
  page: string;
  anchor: string | null;
  before: string;
  after: string;
  chip: Chip;
}
export interface ClaimRow {
  id: string;
  text: string;
  status: "needs_confirmation" | "confirmed" | "backed";
  chip: Chip;
}
export interface RevisionRow {
  id: string;
  label: string;
  chip: Chip;
  current: boolean;
}
const obj = (value: unknown): Record<string, unknown> =>
  value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
const arr = (value: unknown): unknown[] => (Array.isArray(value) ? value : []);
const str = (value: unknown): string | null =>
  typeof value === "string" && value ? value : null;
const num = (value: unknown): number | null =>
  typeof value === "number" && Number.isFinite(value) ? value : null;
/** A page address as a person reads it: its path, never the full URL. */
export function pathOf(url: string): string {
  try {
    const parsed = new URL(url, "https://site.invalid");
    return parsed.pathname || "/";
  } catch {
    return url;
  }
}
const inboundCodes: Record<string, string> = {
  PAGE_MAPPING_REQUIRED: "This page is not set up for edits yet",
  LINK_FIELD_NOT_MAPPED: "This page has no editable link area",
  NO_NATURAL_ANCHOR: "No natural place to add the link",
  PROPOSAL_REJECTED: "The edit did not pass checks",
};
export interface Review {
  words: number;
  floorWords: number | null;
  meetsFloor: boolean | null;
  outline: { level: 2 | 3; text: string }[];
  seoTitle: string | null;
  metaDescription: string | null;
  faqs: { question: string; answer: string }[];
  checks: QualityCheck[];
  links: LinkRow[];
  inbound: InboundEdit[];
  claims: ClaimRow[];
  unresolved: number;
  /** A page already on the site that covers a related topic. Advisory, never blocks approval. */
  similarPage: SimilarPage | null;
  revisions: RevisionRow[];
  prompt: string | null;
}
export interface SimilarPage {
  title: string;
  href: string;
}
function similarPageOf(doc: Record<string, unknown>): SimilarPage | null {
  const overlap = obj(doc.topic_overlap);
  const href = str(overlap.url);
  if (!href) return null;
  return { href, title: str(overlap.title) ?? "Existing page" };
}
export function review(view: ContentView): Review {
  const latest = view.revisions[0];
  const doc = obj(latest?.validation_document);
  const quality = obj(doc.quality);
  const frontmatter = obj(latest?.frontmatter);
  const floorWords = num(obj(quality.floor).minimum_words);
  const words = latest ? wordCount(latest.body) : 0;
  const checks = arr(quality.checks).map((raw): QualityCheck => {
    const check = obj(raw);
    const code = str(check.code) ?? "";
    const passed = check.passed === true;
    const label = checkLabels[code];
    return {
      code,
      passed,
      chip: {
        label: label ? (passed ? label.pass : label.fail) : "Check",
        tone: passed ? "" : "error",
      },
    };
  });
  const links = arr(quality.links).map((raw): LinkRow => {
    const link = obj(raw);
    const verified = link.verified === true;
    return {
      anchor: str(link.anchor) ?? "",
      url: pathOf(str(link.url) ?? ""),
      verified,
      chip: verified
        ? { label: "Verified", tone: "" }
        : { label: "Not verified", tone: "error" },
    };
  });
  const inbound = arr(doc.inbound_links).map((raw): InboundEdit => {
    const edit = obj(raw);
    const proposed = edit.status === "proposed";
    return {
      page: pathOf(str(edit.page_url) ?? ""),
      anchor: str(edit.anchor),
      before: str(edit.before) ?? "",
      after: str(edit.after) ?? "",
      chip: proposed
        ? { label: "Proposed", tone: "neutral" }
        : {
            label:
              inboundCodes[str(edit.code) ?? ""] ?? "No edit could be proposed",
            tone: "warn",
          },
    };
  });
  const claims = arr(doc.claims).map((raw): ClaimRow => {
    const claim = obj(raw);
    const status =
      claim.status === "needs_confirmation" || claim.status === "confirmed"
        ? claim.status
        : "backed";
    return {
      id: str(claim.claim_id) ?? "",
      text: str(claim.text) ?? "",
      status,
      chip:
        status === "needs_confirmation"
          ? { label: "Needs confirmation", tone: "warn" }
          : status === "confirmed"
            ? { label: "Confirmed", tone: "" }
            : { label: "Backed by facts", tone: "" },
    };
  });
  return {
    words,
    floorWords,
    meetsFloor: latest && floorWords !== null ? words >= floorWords : null,
    outline: latest ? outline(latest.body) : [],
    seoTitle: str(frontmatter.seo_title),
    metaDescription: str(frontmatter.description),
    faqs: arr(frontmatter.faqs).flatMap((raw) => {
      const faq = obj(raw);
      const question = str(faq.question);
      const answer = str(faq.answer);
      return question && answer ? [{ question, answer }] : [];
    }),
    checks,
    links,
    inbound,
    claims,
    unresolved: claims.filter((c) => c.status === "needs_confirmation").length,
    similarPage: similarPageOf(doc),
    revisions: view.revisions.map((r, index) => ({
      id: r.id,
      label: `Revision ${r.revision_number}`,
      chip: revisionChip(r.status),
      current: index === 0,
    })),
    prompt: view.briefs[0]?.source_prompt ?? null,
  };
}

/** The exact change an approval signs off on, from the publishing preview. */
export interface ExactChange {
  repository: string;
  branch: string;
  filePath: string;
  kind: "new_file" | "edit";
  kindLabel: string;
}
export function exactChange(
  view: ContentView,
  targetId: string | null,
): ExactChange | null {
  const preview =
    view.publish_preview.find((p) => p.target_id === targetId) ??
    view.publish_preview[0];
  if (!preview) return null;
  return {
    repository: preview.repository_id,
    branch: preview.base_branch,
    filePath: preview.file_path,
    kind: preview.change_kind,
    kindLabel:
      preview.change_kind === "new_file"
        ? "A new file is added"
        : "The existing file is replaced",
  };
}

/** The decision stage an approval applies to, by the revision's typed status. */
export const approvalStage = (status: string): "editorial" | "client" | null =>
  status === "awaiting_editorial"
    ? "editorial"
    : status === "awaiting_client"
      ? "client"
      : null;
