import { z } from "zod";
const uuid =
  "([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})";
const base = `organizations/${uuid}/command-center/reports`;
const month = "(\\d{4}-(?:0[1-9]|1[0-2]))";
const one = `${base}/${month}/(\\d{1,4})`;
const empty = z.object({}).strict();
export const narrativeBody = z
  .object({
    what_changed: z.string().max(4000),
    next_work: z.string().max(4000),
  })
  .strict();
export const generateBody = z
  .object({ month: z.string().regex(/^\d{4}-(0[1-9]|1[0-2])-01$/) })
  .strict();
export const sentBody = z
  .object({ sent_on: z.string().regex(/^\d{4}-\d{2}-\d{2}$/) })
  .strict();
/**
 * Monthly reports through the BFF: the portfolio board, one client's reports, one stored
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
