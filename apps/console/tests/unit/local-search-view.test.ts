import { describe, it, expect } from "vitest";
import fixtures from "../fixtures/phase2.json";
import { adaptLocalSearch } from "../../src/adapters/local-search";
import {
  chartModel,
  momentum,
  overviewTiles,
  pageRows,
  queryRows,
  sourceDetails,
} from "../../src/lib/local-search-view";
import {
  hoursRows,
  keywordText,
  photoRows,
  profileSummary,
  postRows,
} from "../../src/lib/gbp-view";
import { postState, postChips } from "../../src/lib/status";
import { clockText } from "../../src/lib/present";
const org = fixtures.search.organization_id;
const raw =
  /\d{4}-\d{2}-\d{2}T|[0-9a-f]{8}-[0-9a-f]{4}-|[a-z]+_[a-z_]+|^[A-Z]+(_[A-Z]+)+$/;
/** Everything a person could read in a view model must be free of system text. */
function texts(value: unknown): string[] {
  if (typeof value === "string") return [value];
  if (Array.isArray(value)) return value.flatMap(texts);
  if (value && typeof value === "object")
    return Object.entries(value).flatMap(([key, v]) =>
      ["id", "publicationId", "postKey", "url", "postType", "state"].includes(
        key,
      )
        ? []
        : texts(v),
    );
  return [];
}
const search = adaptLocalSearch(fixtures.search, org, org);
describe("Local Search presenters", () => {
  it("never shows system text in what a person reads", () => {
    for (const view of [
      sourceDetails(search),
      overviewTiles(search, null, 28),
      momentum(search),
      queryRows(search),
      pageRows(search),
    ])
      for (const text of texts(view)) expect(text, text).not.toMatch(raw);
  });
  it("turns Google's state into labels, not codes or ISO dates", () => {
    const details = sourceDetails(search);
    expect(details.connection.label).toBe("Reconnect Google");
    expect(details.syncs[0].note).toBe(
      "Google limited the request; it will be retried.",
    );
    expect(details.syncs[0].when).toBe("Sep 29, 2026");
  });
  it("shows a missing number as a reason, and an observed zero as 0", () => {
    const [clicks, impressions, calls] = overviewTiles(search, null, 28);
    expect(clicks.value).toBe("0");
    expect(impressions.missing).toBe(true);
    expect(impressions.value).toBe("No data");
    expect(calls.value).toBe("Unavailable");
  });
  it("charts only days that have a value", () => {
    expect(chartModel([{ day: "2026-10-01", value: 5 }])).toBeNull();
    const chart = chartModel([
      { day: "2026-10-01", value: 0 },
      { day: "2026-10-02", value: 4 },
    ])!;
    expect(chart.labels.map((l) => l.text)).toContain("Oct 1");
  });
});
describe("Business Profile presenters", () => {
  it("writes a below-threshold keyword as a limit, never 0", () => {
    const term = (value: number | null, below: number | null) => ({
      keyword: "k",
      value,
      below_threshold: below,
      is_exact: below === null,
    });
    expect(keywordText(term(null, 15))).toBe("< 15");
    expect(keywordText(term(40, null))).toBe("40");
    expect(keywordText(term(40, 15))).toBe("40+");
    expect(keywordText(term(null, null))).toBe("–");
  });
  it("derives one chip per post from its revision and publication", () => {
    expect(postState("awaiting_approval", null)).toBe("awaiting_approval");
    expect(postState("approved", null)).toBe("approved");
    expect(postState("approved", "verified")).toBe("published");
    expect(postState("approved", "not_published")).toBe("not_published");
    expect(postState("approved", "discarded")).toBe("discarded");
    expect(postState("approved", "reconciliation_required")).toBe(
      "needs_attention",
    );
    expect(postChips.published.label).toBe("Published");
  });
  it("offers only the actions each state allows", () => {
    const post = (status: string, pub: string | null) => ({
      id: "1",
      post_key: "k",
      revision: 1,
      post_type: "standard" as const,
      content: "Hello",
      call_to_action: null,
      event_or_offer: null,
      status,
      publication: pub
        ? {
            id: "p",
            status: pub,
            scheduled_for: null,
            dispatched_at: null,
            provider_post_id: null,
            verified_at: null,
            recovery_allowed: false,
          }
        : null,
    });
    const can = {
      canApprove: true,
      canPublish: true,
      canPropose: true,
      canWrite: true,
    };
    const actions = (status: string, pub: string | null) =>
      postRows({ posts: [post(status, pub)] } as never, can)[0].actions;
    expect(actions("awaiting_approval", null)).toEqual(["approve", "reject"]);
    expect(actions("approved", null)).toEqual(["publish"]);
    expect(actions("approved", "not_published")).toEqual(["repost", "discard"]);
    expect(actions("approved", "verified")).toEqual([]);
    expect(
      postRows({ posts: [post("awaiting_approval", null)] } as never, {
        ...can,
        canApprove: false,
      })[0].actions,
    ).toEqual([]);
  });
  it("only previews secure photo addresses and formats hours", () => {
    const rows = photoRows(
      [
        {
          id: "1",
          media_type: "photo",
          source_reference: "http://insecure.example/a.jpg",
          rights_authority: "Owned by the business",
          status: "awaiting_approval",
          verified_at: null,
        },
      ],
      { canApprove: true, canWrite: true },
    );
    expect(rows[0].url).toBeNull();
    expect(rows[0].actions).toEqual(["approve", "reject"]);
    expect(clockText("16:30:00")).toBe("4:30 PM");
    const hours = hoursRows(
      [
        {
          id: "h",
          service_date: "2026-12-25",
          revision: 1,
          periods: [{ opens: "12:00", closes: "16:00" }],
          source: "console",
          status: "approved",
        },
      ],
      true,
    )[0];
    expect(hours.date).toBe("Friday, December 25, 2026");
    expect(hours.times).toBe("12:00 PM – 4:00 PM");
  });
  it("reads the provider profile as a person would", () => {
    const summary = profileSummary({
      title: "Cococabana",
      phoneNumbers: { primaryPhone: "(858) 555-0142" },
      categories: { primaryCategory: { displayName: "Bar" } },
      regularHours: {
        periods: [
          {
            openDay: "MONDAY",
            openTime: { hours: 9 },
            closeTime: { hours: 17 },
          },
        ],
      },
    });
    expect(summary.rows.map((r) => r.label)).toEqual([
      "Business name",
      "Phone",
      "Primary category",
    ]);
    expect(summary.hours[0]).toEqual({
      day: "Monday",
      text: "9:00 AM – 5:00 PM",
    });
    expect(summary.hours[1].text).toBe("Closed");
  });
});
