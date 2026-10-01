import type { Client, ViewState, MetricPresentation } from "../../types/domain";
import {
  clients,
  reports,
  pageRecords,
  reviewRecords,
  hospitalityMetrics,
} from "./index";
import { pct, scaled } from "../../lib/view";
export function leadsMetrics(c: Client): MetricPresentation[] {
  return [
    ["Total leads", scaled(c.leads), "Selected period"],
    ["Organic search", scaled(c.leads * 0.61), "61% of tracked leads"],
    ["GBP referrals", scaled(c.leads * 0.26), "26% of tracked leads"],
    ["Other sources", scaled(c.leads * 0.13), "13% of tracked leads"],
  ];
}

export function outcomeMetrics(state: ViewState): MetricPresentation[] {
  const periodLabel = (source: string) =>
    source + " · Last " + state.range + " days";
  return [
    [
      "Reservation clicks",
      scaled(132),
      periodLabel("GA4 reserve_click") + " · −8%",
    ],
    [
      "Form submissions",
      scaled(48),
      scaled(12, "GA4 · Last {days} days · {value} event inquiries"),
    ],
    ["Website phone clicks", scaled(106), periodLabel("GA4 phone_click")],
    ["Completed reservations", "Unavailable", "Provider outcome not connected"],
  ];
}

export function searchConsoleMetrics(c: Client): MetricPresentation[] {
  return [
    [
      "Search clicks",
      scaled(c.organic * 0.7),
      pct(c.traffic) + " vs prior period",
    ],
    ["Impressions", scaled(c.organic * 14), "+22% vs prior period"],
    ["Click-through rate", "5.0%", "+0.4 points"],
    ["Average position", (c.rank + 6).toFixed(1), "Organic search results"],
  ];
}

export function gbpMetrics(c: Client): MetricPresentation[] {
  return [
    ["Calls", scaled(c.leads * 1.8), "+21% vs prior period"],
    ["Website clicks", scaled(c.leads * 4.2), "+18% vs prior period"],
    ["Directions", scaled(c.leads * 2.7), "+12% vs prior period"],
    ["Profile completeness", "96%", "Categories and service details verified"],
  ];
}

export function rankingMetrics(c: Client): MetricPresentation[] {
  return [
    ["Average local rank", c.rank, "Across priority queries"],
    ["Top 3 visibility", c.top3 + "%", "Local scan grid"],
    [
      "Top 10 visibility",
      Math.min(98, c.visibility + 19) + "%",
      "Local scan grid",
    ],
    ["Not found", c.notfound + "%", "Outside tracked results"],
  ];
}

export function localSearchMetrics(c: Client): MetricPresentation[] {
  return [
    ["Local visibility", c.visibility + "%", pct(c.change) + " points"],
    ["Top 3 visibility", c.top3 + "%", "Across priority local queries"],
    [
      "Organic search clicks",
      scaled(c.organic * 0.7),
      pct(c.traffic) + " vs prior period",
    ],
    [
      "GBP actions",
      c.gbp === "Disconnected" ? "Unavailable" : scaled(c.leads * 8.7),
      c.gbp === "Disconnected"
        ? "Authorization needs attention"
        : "+18% vs prior period",
    ],
  ];
}

export function hospitalitySearchConsoleMetrics(
  state: ViewState,
): MetricPresentation[] {
  const periodLabel = (source: string) =>
    source + " · Last " + state.range + " days";
  return [
    [
      "Search clicks",
      scaled(hospitalityMetrics.gscClicks),
      periodLabel("Search Console") + " · +24%",
    ],
    [
      "Impressions",
      scaled(hospitalityMetrics.gscImpressions),
      periodLabel("Search Console") + " · +22%",
    ],
    ["Click-through rate", "5.0%", "+0.4 points"],
    ["Indexed pages", "24", "2 utility pages excluded"],
  ];
}

export function hospitalityGbpMetrics(): MetricPresentation[] {
  return [
    ["Calls", scaled(515), "+21%"],
    ["Website clicks", scaled(1201), "+24%"],
    ["Directions", scaled(772), "+19%"],
    ["Profile completeness", "96%", "Brunch category needs verification"],
  ];
}

export function hospitalityRankingMetrics(): MetricPresentation[] {
  return [
    ["Average local rank", "6.2", "Improved 2.1 positions"],
    ["Top 3 visibility", "46%", "+7 points"],
    ["Top 10 visibility", "78%", "+9 points"],
    ["Not found", "10%", "−3 points"],
  ];
}

export function hospitalityLocalSearchMetrics(
  state: ViewState,
): MetricPresentation[] {
  const periodLabel = (source: string) =>
    source + " · Last " + state.range + " days";
  return [
    ["Local visibility", "72%", "+12.4 points"],
    ["Average local rank", "6.2", "5 brunch queries near Top 3"],
    [
      "Search Console clicks",
      scaled(hospitalityMetrics.gscClicks),
      periodLabel("Search Console") + " · +24%",
    ],
    ["GBP actions", scaled(2488), periodLabel("GBP") + " · +22%"],
  ];
}

export function portfolioMetrics(): MetricPresentation[] {
  return [
    ["Local visibility", "56.8%", "+3.5 points vs previous period"],
    ["Website leads", scaled(1345), "+18.6% vs previous period"],
    [
      "New reviews",
      scaled(clients.reduce((s, c) => s + c.newReviews, 0)),
      "4.8 average Google rating",
    ],
    [
      "Reporting attention",
      String(
        reports.filter((r) =>
          ["Missing data", "Needs review"].includes(r.status),
        ).length,
      ),
      "Data gaps and reports to review",
    ],
  ];
}

export function portfolioReportMetrics(): MetricPresentation[] {
  return [
    [
      "Ready",
      reports.filter((r) => r.status === "Ready").length,
      "Available for delivery",
    ],
    [
      "Recently sent",
      reports.filter((r) => r.status === "Sent").length,
      "September reporting cycle",
    ],
    [
      "Upcoming",
      reports.filter((r) => r.status === "Upcoming").length,
      "Next scheduled delivery Oct 1",
    ],
    [
      "Needs attention",
      reports.filter((r) => ["Missing data", "Needs review"].includes(r.status))
        .length,
      "Review or incomplete source data",
    ],
  ];
}

export function reviewMetrics(c: Client): MetricPresentation[] {
  return [
    ["Google rating", c.rating.toFixed(1) + " ★", c.reviews + " total reviews"],
    ["New reviews", scaled(c.newReviews), "Selected period"],
    [
      "Awaiting response",
      reviewRecords.filter((r) => r.client === c.id && r.status !== "Published")
        .length,
      "Includes saved drafts",
    ],
    [
      "Review velocity",
      (c.workspaceProfile === "hospitality"
        ? ((c.newReviews / 30) * 7).toFixed(1)
        : Math.round(c.newReviews / 4)) + " /wk",
      c.workspaceProfile === "hospitality"
        ? "GBP Reviews · 30-day rolling average"
        : "vs previous month",
    ],
  ];
}

export function conversionPathMetrics(): MetricPresentation[] {
  return [
    [
      "Menu Reserve click rate",
      "1.6%",
      "GA4 · reserve_click / organic sessions",
    ],
    ["Event form completion", "2.4%", "GA4 · form_submit / organic sessions"],
    ["Mobile Reserve placement", "Below menu", "Website UX inspection"],
    ["Reservation completion", "Unavailable", "No provider completion source"],
  ];
}

export function conversionMetrics(c: Client): MetricPresentation[] {
  return [
    [
      "Website leads",
      c.website === "Tracking issue" ? "Incomplete" : scaled(c.leads),
      c.website === "Tracking issue"
        ? "Tracking needs attention"
        : pct(c.leadChange ?? c.traffic - 3) + " vs prior period",
    ],
    ["Lead conversion", "5.1%", "+0.3 points"],
    ["Form submissions", scaled(c.leads * 0.62), "Website forms"],
    ["Phone clicks", scaled(c.leads * 0.38), "Tracked click-to-call"],
  ];
}

export function technicalMetrics(c: Client): MetricPresentation[] {
  return [
    ["Technical health", c.health + "/100", c.website],
    ["Indexed pages", "24", "2 excluded by intent"],
    [
      "Broken links",
      c.website === "SEO issue" ? "4" : "0",
      "Latest website scan",
    ],
    ["Structured data", "22 / 24", "2 pages need fuller service markup"],
  ];
}

export function hospitalityTechnicalMetrics(c: Client): MetricPresentation[] {
  return [
    ["Technical health", c.health + "/100", c.website],
    ["Indexed pages", "24", "2 excluded utility pages"],
    [
      "Legacy links",
      c.website === "SEO issue" ? "4" : "0",
      "Private-event redirect chains",
    ],
    ["Restaurant markup", "22 / 24", "2 landing pages need full fields"],
  ];
}

export function websiteMetrics(
  c: Client,
  state: ViewState,
): MetricPresentation[] {
  const periodLabel = (source: string) =>
    source + " · Last " + state.range + " days";
  return [
    [
      c.workspaceProfile === "hospitality"
        ? "Organic sessions"
        : "Organic visits",
      scaled(c.organic),
      c.workspaceProfile === "hospitality"
        ? periodLabel("GA4") + " · +31%"
        : pct(c.traffic) + " vs prior period",
    ],
    [
      "Published pages",
      c.workspaceProfile === "hospitality"
        ? 24
        : pageRecords.filter((p) => p.client === c.id && p.status !== "Draft")
            .length,
      c.workspaceProfile === "hospitality"
        ? "Search Console · latest index coverage"
        : "Shared page templates",
    ],
    [
      "Content in progress",
      "1",
      c.workspaceProfile === "hospitality"
        ? "Brunch page draft"
        : "Resource guide draft",
    ],
    ["Website health", c.health + "/100", c.website],
  ];
}
