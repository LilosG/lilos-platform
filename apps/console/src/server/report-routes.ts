import { z } from "zod";
const uuid =
  "([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})";
const base = `organizations/${uuid}/command-center/reports`;
const month = "\\d{4}-(?:0[1-9]|1[0-2])";
// A period is one month or several ("2026-05_2026-09"); a comparison is previous, year-ago or vs-<months>.
const period = `(${month}(?:_${month})?)`;
const comparison = `(previous|year-ago|vs-${month}(?:_${month})?)`;
const one = `${base}/${period}/${comparison}/(\\d{1,4})`;
const empty = z.object({}).strict();
export const narrativeBody = z
  .object({
    what_changed: z.string().max(4000),
    next_work: z.string().max(4000),
    // Absent leaves the cards as they are.
    result_cards: z
      .array(
        z
          .object({
            figure_keys: z.array(z.string()).min(1).max(2),
            tone: z.enum(["good", "bad", "neutral"]),
            headline: z.boolean(),
            title: z.string().max(80),
            text: z.string().max(500),
          })
          .strict(),
      )
      .max(4)
      .optional(),
  })
  .strict();
const firstOfMonth = z.string().regex(/^\d{4}-(0[1-9]|1[0-2])-01$/);
export const generateBody = z
  .object({
    start_month: firstOfMonth,
    end_month: firstOfMonth,
    comparison: z
      .object({
        basis: z.enum([
          "previous_period",
          "same_period_last_year",
          "custom_baseline",
        ]),
        baseline_start: firstOfMonth.optional(),
        baseline_end: firstOfMonth.optional(),
      })
      .strict(),
  })
  .strict();
export const sentBody = z
  .object({ sent_on: z.string().regex(/^\d{4}-\d{2}-\d{2}$/) })
  .strict();
/**
 * Reports through the BFF: the portfolio board, one client's reports, one stored
 * revision, and the writes (generate, narrative, draft, approve, mark sent).
 */
export const reportRoutes = [
  {
    pattern: /^command-center\/reports\/$/,
    method: "GET",
    upstream: "",
    query: ["month"],
  },
  { pattern: new RegExp(`^${base}/$`), method: "GET", upstream: "", query: [] },
  {
    pattern: new RegExp(`^${base}/generate/$`),
    method: "POST",
    upstream: "",
    query: [],
    body: generateBody,
  },
  { pattern: new RegExp(`^${one}/$`), method: "GET", upstream: "", query: [] },
  {
    pattern: new RegExp(`^${one}/narrative/$`),
    method: "PUT",
    upstream: "",
    query: [],
    body: narrativeBody,
  },
  {
    pattern: new RegExp(`^${one}/draft-narrative/$`),
    method: "POST",
    upstream: "",
    query: [],
    body: empty,
  },
  {
    pattern: new RegExp(`^${one}/approve/$`),
    method: "POST",
    upstream: "",
    query: [],
    body: empty,
  },
  {
    pattern: new RegExp(`^${one}/mark-sent/$`),
    method: "POST",
    upstream: "",
    query: [],
    body: sentBody,
  },
] as const;
