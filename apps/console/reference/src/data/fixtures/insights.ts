import type { Client, Insight } from "../../types/domain";
export function clientInsight(c: Client): Insight {
  if (c.website === "Tracking issue")
    return {
      title: "Lead data is incomplete. Traffic trends remain available.",
      description:
        "Conversion events have been silent for 72 hours. Restore tracking before judging lead performance.",
      area: "Leads",
      section: "Overview",
    };
  if (c.gbp === "Disconnected")
    return {
      title: "GBP performance is missing while authorization is expired.",
      description:
        "Local visibility fell " +
        Math.abs(c.change) +
        " points. Reconnect the profile to separate data gaps from performance losses.",
      area: "Local Search",
      section: "Google Business Profile",
    };
  if (c.id === "8")
    return {
      title:
        "Menu traffic is growing, but reservation conversion has room to improve.",
      description:
        "The menu page attracted 2,840 organic visits. Just 1.6% clicked through to reserve.",
      area: "Website & Content",
      section: "Conversions",
    };
  if (c.change < 0)
    return {
      title: "Ranking declines are concentrated in service queries.",
      description:
        "Local visibility fell " +
        Math.abs(c.change) +
        " points alongside a " +
        Math.abs(c.traffic) +
        "% traffic decline. Inspect the service links and affected queries.",
      area: "Local Search",
      section: "Technical",
    };
  return {
    title:
      "Organic traffic " +
      (c.traffic > 0 ? "increased" : "declined") +
      " " +
      Math.abs(c.traffic) +
      "% in this period.",
    description:
      "Local visibility " +
      (c.change > 0 ? "improved" : "declined") +
      " " +
      Math.abs(c.change) +
      " points. " +
      (c.rank < 12
        ? "Five priority queries are within striking distance of the Top 3."
        : "Focus on queries already reaching the Top 10 before adding more content."),
    area: "Local Search",
    section: "Rankings",
  };
}
