import { z } from "zod";
const uuid =
  "([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})";
const platform = `platform/organizations`;
const org = `organizations/${uuid}`;
const route = (
  pattern: string,
  method: "GET" | "POST",
  body?: z.ZodType,
  query: string[] = [],
) => ({
  pattern: new RegExp(`^${pattern}/$`),
  method,
  upstream: "",
  query,
  ...(body ? { body } : {}),
});
/** Every lifecycle change names the version it was decided against, so a stale screen is refused. */
export const transition = z
  .object({ expected_version: z.number().int().min(1) })
  .strict();
export const removal = z
  .object({
    confirm_name: z.string().min(1).max(200),
    reason: z.string().min(1).max(500).optional(),
  })
  .strict();
/** What a business fact may hold; the API validates the value against its type again. */
const factValue = z.union([
  z.string().min(1).max(1000),
  z.array(z.string().min(1).max(300)).min(1).max(100),
  z.record(z.string(), z.string().max(300).nullable()),
]);
export const factProposal = z
  .object({
    fact_identity: z.uuid().optional(),
    location_id: z.uuid().nullable().optional(),
    fact_key: z.enum([
      "business.name",
      "business.website",
      "business.address",
      "brand.approved_claims",
    ]),
    value_type: z.enum(["string", "object", "string_list"]),
    value: factValue,
    source: z.literal("console"),
    authority: z.literal("operator_verified"),
    change_reason: z.string().min(1).max(1000),
  })
  .strict();
export const factDecision = z
  .object({ decision: z.enum(["approve", "reject"]) })
  .strict();
const lifecycle = [
  "activate",
  "pause",
  "close-temporarily",
  "close-permanently",
  "archive",
];
/**
 * Administration and Settings through the BFF: the platform's client lifecycle, a client's
 * locations and their lifecycle, and the client's governed business facts.
 */
export const adminRoutes = [
  route(platform, "GET", undefined, ["limit", "offset"]),
  route(`${platform}/${uuid}/removal`, "GET"),
  route(`${platform}/${uuid}/locations`, "GET", undefined, ["limit", "offset"]),
  route(`${platform}/${uuid}/start-offboarding`, "POST", transition),
  route(`${platform}/${uuid}/archive`, "POST", transition),
  route(`${platform}/${uuid}/remove`, "POST", removal),
  route(`${org}/locations`, "GET", undefined, ["limit", "offset"]),
  ...lifecycle.map((step) =>
    route(`${org}/locations/${uuid}/${step}`, "POST", transition),
  ),
  route(`${org}/business-facts/effective`, "GET"),
  route(`${org}/business-facts/candidates`, "GET"),
  route(`${org}/business-facts`, "POST", factProposal),
  route(`${org}/business-facts/${uuid}/decision`, "POST", factDecision),
] as const;
