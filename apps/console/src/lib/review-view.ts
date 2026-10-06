import type { ReviewDetailView, ReviewsView } from "../adapters/reviews";
import { dateText, humanize, initials } from "./present";
import {
  approvalChip,
  connectionChips,
  connectionState,
  type Chip,
  type Tone,
} from "./status";

type Item = ReviewsView["items"][number];
type Source = ReviewDetailView["source"];

/** What shows where a name goes. A reviewer is never "unavailable". */
export interface Reviewer {
  kind: Item["reviewer_identity"];
  name: string;
  initials: string;
  /** Only an https picture is ever loaded. */
  photo: string | null;
}
export function reviewer(item: Item): Reviewer {
  if (item.reviewer_identity === "named" && item.reviewer_display_name) {
    const photo = item.reviewer_photo_url;
    return {
      kind: "named",
      name: item.reviewer_display_name,
      initials: initials(item.reviewer_display_name) || "G",
      photo: photo?.startsWith("https://") ? photo : null,
    };
  }
  return item.reviewer_identity === "anonymous"
    ? { kind: "anonymous", name: "Google user", initials: "", photo: null }
    : { kind: "unknown", name: "Google reviewer", initials: "G", photo: null };
}

export interface MetricCell {
  label: string;
  value: string;
  description: string;
  missing?: boolean;
}
const EM_DASH = "—";
const notTracked = "Not tracked yet";
/** A missing number is a dash with a reason, never 0. */
function cell(
  label: string,
  value: number | null,
  text: (n: number) => string,
  description: string,
  hint: string,
): MetricCell {
  return value === null
    ? { label, value: EM_DASH, description: hint, missing: true }
    : { label, value: text(value), description };
}
export function reviewMetrics(v: ReviewsView): MetricCell[] {
  const hint = v.can_ingest ? "Import reviews to see this" : notTracked;
  return [
    cell(
      "Total reviews",
      v.inventory_count,
      (n) => n.toLocaleString("en-US"),
      "Imported from Google",
      hint,
    ),
    cell(
      "Average rating",
      v.inventory_count === 0 ? null : v.average_rating,
      (n) => n.toFixed(1),
      "Out of 5 stars",
      hint,
    ),
    cell(
      "Awaiting response",
      v.awaiting_response_count,
      (n) => n.toLocaleString("en-US"),
      "Reviews with no published reply",
      hint,
    ),
  ];
}

export interface SourceView {
  chip: Chip;
  rows: { name: string; chip: Chip; detail: string }[];
}
const freshChip: Record<Source["freshness"], Chip> = {
  fresh: { label: "Up to date", tone: "" },
  stale: { label: "Out of date", tone: "warn" },
  unavailable: { label: "Not imported yet", tone: "neutral" },
};
const qualityChip: Record<Source["quality"], Chip> = {
  partial: { label: "Partial", tone: "warn" },
  unavailable: { label: "Not available", tone: "neutral" },
};
/** One chip for the page header; the rows are what its Details dialog lists. */
export function sourceView(source: ReviewsView["source"]): SourceView {
  const state = connectionState(source?.connection_status ?? null);
  const connection = connectionChips[state];
  const mapped = source?.mapping_status === "confirmed";
  const mapping: Chip = mapped
    ? { label: "Confirmed", tone: "" }
    : { label: "Not set up", tone: "warn" };
  const freshness = freshChip[source?.freshness ?? "unavailable"];
  const quality = qualityChip[source?.quality ?? "unavailable"];
  const chip: Chip =
    state !== "connected"
      ? connection
      : !mapped
        ? { label: "Location not matched", tone: "warn" }
        : freshness.tone === ""
          ? { label: "Reviews up to date", tone: "" }
          : {
              label: `Reviews ${freshness.label.toLowerCase()}`,
              tone: freshness.tone as Tone,
            };
  return {
    chip,
    rows: [
      {
        name: "Google connection",
        chip: connection,
        detail:
          state === "connected"
            ? "Reviews are read from the connected Google account."
            : "Reconnect Google in Integrations to keep reviews current.",
      },
      {
        name: "Business location",
        chip: mapping,
        detail: mapped
          ? "This location is matched to its Google Business Profile."
          : "Match this location to a Google Business Profile in Integrations.",
      },
      {
        name: "Last import",
        chip: freshness,
        detail: source?.last_ingested_at
          ? `Imported ${dateText(source.last_ingested_at)}`
          : "Reviews have not been imported for this location.",
      },
      {
        name: "Coverage",
        chip: quality,
        detail:
          "Totals describe the reviews imported so far, which may be fewer than Google shows.",
      },
    ],
  };
}

/** Facts a response may draw on: a readable name and value, never a key or JSON. */
export function factLabel(value: unknown): string {
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean")
    return String(value);
  return "On file";
}

type Response = ReviewDetailView["responses"][number];
const responseChips: Record<Response["status"], Chip> = {
  draft: { label: "Draft", tone: "neutral" },
  generated: { label: "Draft", tone: "neutral" },
  awaiting_approval: approvalChip("awaiting_approval"),
  approved: approvalChip("approved"),
  publishing: approvalChip("publishing"),
  published: approvalChip("published"),
  failed: { label: "Needs attention", tone: "error" },
  rejected: approvalChip("rejected"),
  superseded: { label: "Replaced", tone: "neutral" },
  reconciliation_required: { label: "Needs attention", tone: "error" },
};
export const responseChip = (status: Response["status"]): Chip =>
  responseChips[status];
/** What a person should do or know about a response, from its typed state. */
export const responseNote: Partial<Record<Response["status"], string>> = {
  awaiting_approval: "Approve this exact wording to allow it to be published.",
  approved: "Approved. Publish it to post this reply on Google.",
  publishing: "Publishing. It shows as published once Google confirms it.",
  failed:
    "Google did not accept this reply. Check the review on Google before trying again.",
  reconciliation_required:
    "Google could not confirm this reply. Check the review on Google before trying again.",
};
const eventText: Record<string, string> = {
  "reviews.review.ingested": "Review imported",
  "reviews.response.drafted": "Response drafted",
  "reviews.response.approved": "Response approved",
  "reviews.response.publication_requested": "Publishing requested",
  "reviews.response.published": "Response published",
  "reviews.response.provider_observed": "Reply seen on Google",
};
export const eventLabel = (type: string): string =>
  eventText[type] ?? humanize(type.split(".").slice(-1)[0] ?? type);
export const actorLabel = (type: string): string =>
  ({ user: "A person", system: "The system" })[type] ?? "The system";
export const resultLabel = (result: string): string =>
  result === "succeeded" ? "" : humanize(result);
