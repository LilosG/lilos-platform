import type { Client, DisplayValue, ProductArea } from "../../types/domain";
import { pct, scaled } from "../../lib/view";
export interface SnapshotMetric {
  label: string;
  value: DisplayValue;
  description: DisplayValue;
  area: ProductArea;
  section?: string;
}
export function snapshotMetrics(c: Client): SnapshotMetric[] {
  if (c.workspaceProfile === "hospitality")
    return [
      {
        label: "Local visibility",
        value: "72%",
        description: "Latest local scan · +12.4 points",
        area: "Local Search",
        section: "Rankings",
      },
      {
        label: "Average local rank",
        value: "6.2",
        description: "Local scan · Top 3 46% · Top 10 78%",
        area: "Local Search",
        section: "Rankings",
      },
      {
        label: "GBP actions",
        value: scaled(2488),
        description: "GBP · Last 30 days · +22%",
        area: "Local Search",
        section: "Google Business Profile",
      },
      {
        label: "Google rating",
        value: "4.8 ★",
        description: scaled(
          18,
          "GBP Reviews · Last {days} days · +{value} · 342 total",
        ),
        area: "Reviews",
      },
      {
        label: "Organic visits",
        value: scaled(c.organic),
        description: "+31% vs previous period",
        area: "Website & Content",
      },
      {
        label: "Reservation clicks",
        value: scaled(132),
        description: "GA4 reserve_click · Last 30 days · −8%",
        area: "Leads",
      },
    ];
  return [
    {
      label: "Local visibility",
      value: c.visibility + "%",
      description: pct(c.change) + " points",
      area: "Local Search",
    },
    {
      label: "Average local rank",
      value: c.rank,
      description: c.top3 + "% Top 3 visibility",
      area: "Local Search",
    },
    {
      label: "GBP actions",
      value: c.gbp === "Disconnected" ? "Unavailable" : scaled(c.leads * 8.7),
      description:
        c.gbp === "Disconnected"
          ? "Reconnect to restore data"
          : "+18% · calls, clicks, directions",
      area: "Local Search",
    },
    {
      label: "Google rating",
      value: c.rating.toFixed(1) + " ★",
      description: scaled(c.newReviews, "+{value} new reviews"),
      area: "Reviews",
    },
    {
      label: "Organic visits",
      value: scaled(c.organic),
      description: pct(c.traffic) + " vs prior period",
      area: "Website & Content",
    },
    {
      label: "Website leads",
      value: c.website === "Tracking issue" ? "Incomplete" : scaled(c.leads),
      description:
        c.website === "Tracking issue"
          ? "Tracking needs attention"
          : pct(
              c.leadChange ?? (c.traffic > 0 ? c.traffic - 3 : c.traffic - 2),
            ) + " vs prior period",
      area: "Leads",
    },
  ];
}
