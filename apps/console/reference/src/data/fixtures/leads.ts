import type { Lead } from "../../types/domain";
import { clients } from "./clients";
export const sampleContacts = [
  "Alex Morgan",
  "Jordan Lee",
  "Taylor Brooks",
  "Casey Reed",
] as const;
export const eventInquiries = [
  "Birthday brunch · 12 guests",
  "Corporate gathering · 20 guests",
  "Private dinner · 16 guests",
  "Weekend celebration · 10 guests",
] as const;
export const leads: Lead[] = clients.flatMap((c) =>
  sampleContacts.map((contact, i) => ({
    id: c.id + "-" + i,
    clientId: c.id,
    contact,
    inquiry:
      c.workspaceProfile === "hospitality"
        ? eventInquiries[i]
        : c.category === "Restaurant"
          ? "Private event inquiry"
          : c.category === "Electrician"
            ? "Service estimate"
            : "Service inquiry",
    message: `I’d like to learn more about your ${c.category.toLowerCase()} services and availability. Please contact me with the next steps.`,
    displaySource:
      i % 2
        ? c.workspaceProfile === "hospitality"
          ? "GBP website click"
          : "GBP website link"
        : "Organic search",
    source: i % 2 ? "GBP website link" : "Organic search",
    received: "Sep " + (29 - i),
    status: i === 0 ? "New" : "Contacted",
  })),
);
