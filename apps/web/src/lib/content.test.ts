import { describe, expect, it } from "vitest";

import {
  CONTENT_REQUIRED_FACT_KEYS,
  isContentOpportunityActionable,
} from "./content";

describe("Content workflow contracts", () => {
  it("offers decisions only for statuses accepted by the API", () => {
    expect(isContentOpportunityActionable("identified")).toBe(true);
    expect(isContentOpportunityActionable("validated")).toBe(true);
    expect(isContentOpportunityActionable("accepted")).toBe(false);
    expect(isContentOpportunityActionable("rejected")).toBe(false);
  });

  it("grounds briefs in the current Content product fact requirements", () => {
    expect(CONTENT_REQUIRED_FACT_KEYS).toEqual([
      "business.name",
      "brand.approved_claims",
    ]);
  });
});
