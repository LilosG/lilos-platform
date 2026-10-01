import type { Integration, Client } from "../../types/domain";
const initialSystems: Integration[] = [
  [
    "Google Business Profile",
    "GBP",
    "Needs attention",
    11,
    "1 account authorization expired",
    "Profile updates and performance sync",
  ],
  [
    "Google Search Console",
    "GSC",
    "Connected",
    12,
    "Last sync 18 minutes ago",
    "Search queries, clicks and index coverage",
  ],
  [
    "Google Analytics 4",
    "GA4",
    "Needs attention",
    10,
    "1 tracking error · 1 not configured",
    "Traffic, conversion events and lead trends",
  ],
];

import { clients } from "./clients";
export function systemHealth(currentClients: readonly Client[]): Integration[] {
  return initialSystems.map((system, i) => {
    if (i !== 0 && i !== 2) return system;
    const missing = currentClients.filter((c) =>
      i === 0 ? c.gbp !== "Healthy" : c.integration !== "Connected",
    ).length;
    return [
      system[0],
      system[1],
      missing ? "Needs attention" : "Connected",
      12 - missing,
      missing
        ? i === 0
          ? missing + " account authorization expired"
          : missing + " clients need source or tracking setup"
        : i === 0
          ? "All accounts connected"
          : "All sources reporting",
      system[5],
    ];
  });
}
export const systems = systemHealth(clients);

export const reportingAutomationHealth: Integration = [
  "Reporting automations",
  "RPT",
  "Error",
  11,
  "1 report job needs data recovery",
  "Monthly summaries and delivery schedules",
];
