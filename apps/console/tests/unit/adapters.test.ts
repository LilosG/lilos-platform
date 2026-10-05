import { it, expect } from "vitest";
import {
  adaptOpportunities,
  adaptOpportunityList,
  adaptAttention,
  adaptDetail,
} from "../../src/adapters/opportunities";
const org = "11111111-1111-4111-8111-111111111111",
  id = "22222222-2222-4222-8222-222222222222";
const row = {
  id: `seo_opportunity:${id}`,
  source_kind: "seo_opportunity",
  kind: "seo",
  source_id: id,
  organization_id: org,
  client: { organization_id: org, name: "Alpha", slug: "alpha" },
  location_id: null,
  website_id: org,
  page_id: null,
  classification: "Issue",
  source_type: "missing_meta_description",
  status: "identified",
  priority: null,
  evidence: { quality: "partial", clicks: null },
  score_explanation: {},
  observed_at: "2026-09-30T00:00:00Z",
  evidence_context: {
    source: "crawl",
    quality: "partial",
    freshness_at: null,
    period_start: null,
    period_end: null,
    limitation_code: null,
  },
  priority_band: null,
  headline: null,
  confidence: null,
  evidence_summary: {
    source: "crawl",
    signal: "missing_meta_description",
    metrics: [],
    source_count: null,
  },
  next_action: "request_recommendation",
  latest_revision_status: null,
  site_change: "not_configured",
  site_change_reason: "SITE_CHANGES_NOT_CONFIGURED",
};
it("preserves canonical namespaced identity, null, and partial evidence", () => {
  const result = adaptOpportunities({ data: [row], next_offset: null }, org);
  expect(result[0]).toEqual(row);
});
it.each([
  { ...row, organization_id: id },
  { ...row, id: "13" },
  { ...row, classification: "Made up" },
])("rejects unsafe source projection", (unsafe) =>
  expect(() =>
    adaptOpportunities({ data: [unsafe], next_offset: null }, org),
  ).toThrow(),
);
it("retains operational state independently from opportunity", () => {
  const item = {
    id: `workflow_run:${id}:retry_scheduled`,
    source_id: id,
    opportunity_id: id,
    reason: "retry_scheduled",
    status: "retry_scheduled",
    code: null,
  };
  expect(adaptAttention({ data: [item], next_offset: null })).toEqual([item]);
  expect(() =>
    adaptAttention({
      data: [{ ...item, reason: "dismissed" }],
      next_offset: null,
    }),
  ).toThrow();
});
it("rejects source-ID substitution in canonical detail", () =>
  expect(() =>
    adaptDetail(
      {
        data: row,
        page_url: null,
        kind: "seo",
        recommendations: [],
        runs: [],
        growth: null,
        content: null,
        history: null,
        live_check: null,
        can_recommend: false,
        can_approve: false,
        correlation_id: "c",
      },
      org,
      org,
    ),
  ).toThrow());

const growthId = "33333333-3333-4333-8333-333333333333";
const growth = {
  ...row,
  id: `growth_initiative:${growthId}`,
  source_kind: "growth_initiative",
  kind: "growth",
  source_id: growthId,
  website_id: null,
  page_id: null,
  site_change: "not_applicable",
  site_change_reason: null,
};
it("lists every kind and keeps each client's own identity", () => {
  const view = adaptOpportunityList(
    { data: [row, growth], next_offset: 50, kinds_unavailable: ["content"] },
    null,
    [org],
  );
  expect(view.items.map((item) => item.kind)).toEqual(["seo", "growth"]);
  expect(view.next).toBe(50);
  expect(view.kindsUnavailable).toEqual(["content"]);
});
it.each([
  [
    "a client outside the caller's scope",
    {
      ...row,
      client: { ...row.client, organization_id: id },
      organization_id: id,
    },
  ],
  ["an id that disagrees with its kind", { ...row, kind: "growth" }],
  [
    "a client that is not the row's organization",
    { ...row, client: { ...row.client, organization_id: id } },
  ],
])("rejects %s", (_name, unsafe) =>
  expect(() =>
    adaptOpportunityList(
      { data: [unsafe], next_offset: null, kinds_unavailable: [] },
      null,
      [org],
    ),
  ).toThrow(),
);
it("requires the kind-specific section of the detail", () =>
  expect(() =>
    adaptDetail(
      {
        kind: "growth",
        data: growth,
        page_url: null,
        recommendations: [],
        runs: [],
        growth: null,
        content: null,
        history: [],
        live_check: null,
        can_recommend: false,
        can_approve: false,
        correlation_id: "c",
      },
      org,
      growthId,
    ),
  ).toThrow());
