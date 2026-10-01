import type { ConversionEvent } from "../../types/domain";
export const conversionEvents: ConversionEvent[] = [
  {
    name: "reserve_click",
    label: "Reservation click",
    description:
      "The visitor followed the Reserve link. This measures booking intent, not completion.",
    source: "GA4 · Booking links",
    count: 132,
    completedOutcome: false,
  },
  {
    name: "private_event_submit",
    label: "Private-event inquiry",
    description: "A visitor submitted the private-events inquiry form.",
    source: "GA4 · Private-events form",
    count: 12,
    completedOutcome: false,
  },
  {
    name: "contact_submit",
    label: "Contact form",
    description: "A visitor submitted a contact or general inquiry form.",
    source: "GA4 · Website forms",
    count: 36,
    completedOutcome: false,
  },
  {
    name: "phone_click",
    label: "Website phone click",
    description:
      "The visitor activated a website click-to-call link. A completed call is not confirmed.",
    source: "GA4 · Phone links",
    count: 106,
    completedOutcome: false,
  },
  {
    name: "GBP call interactions",
    label: "GBP calls",
    description:
      "Google Business Profile call interactions. These are separate from website phone-click events.",
    source: "Google Business Profile",
    count: 515,
    completedOutcome: false,
  },
];
