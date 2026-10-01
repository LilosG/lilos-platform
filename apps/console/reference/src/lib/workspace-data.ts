import type { Client } from "../types/domain";
import {
  growthWorkspaces,
  type GrowthOpportunityKey,
} from "../data/fixtures/growthWorkspaces";
import { opportunities } from "../data/fixtures/opportunities";
export function growthWorkspace(client: Client) {
  const fixture = growthWorkspaces[client.id];
  if (!fixture)
    throw new Error(`Missing growth workspace fixture: ${client.slug}`);
  return fixture;
}
export function growthOpportunityId(
  client: Client,
  key: GrowthOpportunityKey,
): number {
  const id = growthWorkspace(client).opportunityIds[key];
  const opportunity = opportunities.find(
    (o) => o.id === id && o.client === Number(client.id) - 1,
  );
  if (!opportunity)
    throw new Error(`Invalid Opportunity relationship: ${client.slug}/${key}`);
  return opportunity.id;
}
