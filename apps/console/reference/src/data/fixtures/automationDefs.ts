import type { AutomationDefinition } from "../../types/domain";
export const automationDefs: AutomationDefinition[] = [
  {
    name: "GBP performance refresh",
    frequency: "Daily · 6:00 AM",
    next: "Sep 30 · 6:00 AM",
    last: "Today · 6:00 AM",
    source: "Google Business Profile",
  },
  {
    name: "Review monitoring",
    frequency: "Every 30 minutes",
    next: "Today · 5:30 PM",
    last: "Today · 5:00 PM",
    source: "Google Business Profile · Reviews",
  },
  {
    name: "Local ranking scan",
    frequency: "Weekly · Monday",
    next: "Oct 5 · 7:00 AM",
    last: "Sep 28 · 7:00 AM",
    source: "Ranking scans",
  },
  {
    name: "Website health check",
    frequency: "Daily · 5:00 AM",
    next: "Sep 30 · 5:00 AM",
    last: "Today · 5:00 AM",
    source: "Website monitoring",
  },
  {
    name: "Monthly client report",
    frequency: "Monthly · 1st",
    next: "Oct 1 · 8:00 AM",
    last: "Sep 28 · 8:00 AM",
    source: "Reporting data",
  },
];
