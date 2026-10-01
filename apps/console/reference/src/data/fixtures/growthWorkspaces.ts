import { hospitalityMetrics, hospitalityObservations } from "./measurements";
import { hospitalitySearchQueries } from "./hospitalitySearchQueries";
import type { SearchQuery } from "../../types/domain";
export interface GrowthWorkspaceFixture {
  metrics: typeof hospitalityMetrics;
  observations: typeof hospitalityObservations;
  queries: SearchQuery[];
  opportunityIds: Record<GrowthOpportunityKey, number>;
}
export type GrowthOpportunityKey =
  | "brunch-category"
  | "reservation-path"
  | "brunch-demand"
  | "private-event-content"
  | "legacy-event-links"
  | "restaurant-markup"
  | "review-request"
  | "reservation-outcomes";
/** Complete Revision 10 growth coverage; additional client fixtures register here. */
export const growthWorkspaces: Record<string, GrowthWorkspaceFixture> = {
  "1": {
    metrics: hospitalityMetrics,
    observations: hospitalityObservations,
    queries: hospitalitySearchQueries,
    opportunityIds: {
      "brunch-category": 4,
      "reservation-path": 13,
      "brunch-demand": 14,
      "private-event-content": 15,
      "legacy-event-links": 16,
      "restaurant-markup": 18,
      "review-request": 17,
      "reservation-outcomes": 19,
    },
  },
};
