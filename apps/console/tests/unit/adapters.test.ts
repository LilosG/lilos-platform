import { it, expect } from "vitest";
import {
  adaptOpportunities,
  adaptAttention,
  adaptDetail,
} from "../../src/adapters/opportunities";
const org = "11111111-1111-4111-8111-111111111111",
  id = "22222222-2222-4222-8222-222222222222";
const row = {
  id: `seo_opportunity:${id}`,
  source_kind: "seo_opportunity",
  source_id: id,
  organization_id: org,
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
        recommendations: [],
        runs: [],
        can_recommend: false,
        can_approve: false,
        correlation_id: "c",
      },
      org,
      org,
    ),
  ).toThrow());
