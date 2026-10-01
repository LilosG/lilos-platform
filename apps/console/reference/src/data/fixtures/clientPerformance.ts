import type { Client, Ranking, SearchQuery } from "../../types/domain";
import {
  serviceRankingQueries,
  organicDemandQueries,
  conversionPages,
} from "./presentation";
export interface ClientRanking extends Omit<Ranking, "prior"> {
  visibilityChange: number;
}
export function clientRankings(client: Client): ClientRanking[] {
  return serviceRankingQueries(client).map((query, index) => ({
    query,
    rank: Math.max(1, Math.round(client.rank + index * 2 - 3)),
    top3: Math.max(0, client.top3 - index * 6),
    top10: Math.min(100, client.visibility + 12 - index * 4),
    visibilityChange: client.change - index,
  }));
}
export function organicSearchDemand(
  client: Client,
): Pick<SearchQuery, "query" | "clicks" | "impressions" | "position">[] {
  return organicDemandQueries(client).map((query, index) => ({
    query,
    clicks: (client.organic * 0.14) / (index + 1),
    impressions: (client.organic * 2.4) / (index + 1),
    position: Number((client.rank + index + 4).toFixed(1)),
  }));
}
export interface PageConversion {
  name: string;
  organic: number;
  actions: number;
  rate: string;
}
export function pageConversions(client: Client): PageConversion[] {
  return conversionPages(client).map((name, index) => ({
    name,
    organic: client.organic / (index + 2),
    actions: client.leads / (index + 2),
    rate: index === 2 && client.category === "Restaurant" ? "1.6%" : "5.1%",
  }));
}
