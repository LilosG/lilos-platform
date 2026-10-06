import { z } from "zod";
import { leadRoutes } from "./lead-routes";
import { websiteRoutes } from "./website-routes";
import { reviewRoutes } from "./review-routes";
import { searchRoutes } from "./search-routes";
import {
  assertMutation,
  boundedBody,
  boundedBytes,
  privateHeaders,
} from "./security";
import type { paths } from "@lilos/contracts/api";
const uuid =
  "([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})";
const field = z.enum([
  "seo_title",
  "meta_description",
  "h1",
  "body_section",
  "schema",
  "internal_link",
]);
const revise = z
  .object({
    edits: z
      .array(
        z
          .object({ field, proposed_value: z.string().min(1).max(10000) })
          .strict(),
      )
      .min(1)
      .max(20),
  })
  .strict();
const decision = z.object({ approve: z.boolean() }).strict();
const contentDecision = z.object({ accept: z.boolean() }).strict();
type DecisionBody =
  paths["/api/v1/organizations/{organization_id}/seo/recommendations/{revision_id}/decision"]["post"]["requestBody"]["content"]["application/json"];
export const routes = [
  ...searchRoutes,
  ...leadRoutes,
  ...websiteRoutes,
  ...reviewRoutes,
  { pattern: /^me\/$/, method: "GET", upstream: "/api/v1/me", query: [] },
  {
    pattern: /^command-center\/(portfolio|clients)\/$/,
    method: "GET",
    upstream: "",
    query: ["days"],
  },
  {
    pattern: new RegExp(`^command-center/clients/${uuid}/overview/$`),
    method: "GET",
    upstream: "",
    query: ["days"],
  },
  {
    pattern: /^me\/organizations\/$/,
    method: "GET",
    upstream: "/api/v1/me/organizations",
    query: [],
  },
  {
    pattern: /^command-center\/opportunities\/$/,
    method: "GET",
    upstream: "",
    query: ["limit", "offset", "organization_id", "kind", "priority", "state"],
  },
  {
    pattern: new RegExp(
      `^organizations/${uuid}/command-center/opportunities/$`,
    ),
    method: "GET",
    upstream: "",
    query: ["limit", "offset", "kind", "priority", "state"],
  },
  {
    pattern: new RegExp(`^organizations/${uuid}/command-center/attention/$`),
    method: "GET",
    upstream: "",
    query: ["limit", "offset"],
  },
  {
    pattern: new RegExp(
      `^organizations/${uuid}/command-center/opportunities/${uuid}/$`,
    ),
    method: "GET",
    upstream: "",
    query: [],
  },
  {
    pattern: new RegExp(
      `^organizations/${uuid}/seo/opportunities/${uuid}/hermes-run/$`,
    ),
    method: "GET",
    upstream: "",
    query: [],
  },
  {
    pattern: new RegExp(
      `^organizations/${uuid}/seo/opportunities/${uuid}/hermes-run/$`,
    ),
    method: "POST",
    upstream: "",
    query: [],
    body: z.object({}).strict(),
  },
  {
    pattern: new RegExp(
      `^organizations/${uuid}/seo/recommendations/${uuid}/revise/$`,
    ),
    method: "POST",
    upstream: "",
    query: [],
    body: revise,
  },
  {
    pattern: new RegExp(
      `^organizations/${uuid}/seo/recommendations/${uuid}/decision/$`,
    ),
    method: "POST",
    upstream: "",
    query: [],
    body: decision,
  },
  {
    // Hermes growth plans are approved or rejected through the existing growth endpoint.
    pattern: new RegExp(`^organizations/${uuid}/growth/${uuid}/decision/$`),
    method: "POST",
    upstream: "",
    query: [],
    body: decision,
  },
  {
    pattern: new RegExp(
      `^organizations/${uuid}/content/opportunities/${uuid}/decision/$`,
    ),
    method: "POST",
    upstream: "",
    query: [],
    body: contentDecision,
  },
] as const;
const uuidKeys = new Set([
  "website_id",
  "location_id",
  "target_id",
  "organization_id",
]);
const enumQuery: Record<string, readonly string[]> = {
  period: ["7d", "28d", "90d", "month"],
  kind: ["seo", "content", "growth"],
  priority: ["high", "medium", "low"],
  state: ["open", "done"],
};
/** One typed rule per query key; anything unlisted fails closed. */
function queryValid(key: string, value: string): boolean {
  if (key === "month") return /^\d{4}-(0[1-9]|1[0-2])$/.test(value);
  if (uuidKeys.has(key)) return z.uuid().safeParse(value).success;
  if (key in enumQuery) return enumQuery[key].includes(value);
  if (!/^\d+$/.test(value)) return false;
  if (key === "days") return [7, 28, 90].includes(Number(value));
  if (key === "limit") return Number(value) >= 1 && Number(value) <= 100;
  return Number(value) <= 100000;
}
export class APIError extends Error {
  constructor(
    public status: number,
    public code: string,
  ) {
    super(code);
  }
}
export async function forward(
  request: Request,
  path: string,
  locals: App.Locals,
  fetcher: typeof fetch = fetch,
): Promise<Response> {
  const response = (code: string, status: number) =>
    new Response(
      JSON.stringify({ code, correlation_id: locals.correlationId }),
      {
        status,
        headers: {
          ...privateHeaders,
          "Content-Type": "application/json",
          "X-Correlation-ID": locals.correlationId,
        },
      },
    );
  const candidates = routes.filter((route) => route.pattern.test(path));
  if (!candidates.length) return response("ROUTE_NOT_FOUND", 404);
  const route = candidates.find((route) => route.method === request.method);
  if (!route) return response("METHOD_NOT_ALLOWED", 405);
  if (!locals.token) return response("AUTH_REQUIRED", 401);
  const query = new URL(request.url).searchParams;
  for (const [key, value] of query) {
    if (
      !(route.query as readonly string[]).includes(key) ||
      query.getAll(key).length !== 1 ||
      !queryValid(key, value)
    )
      return response("QUERY_INVALID", 400);
  }
  let body: string | Uint8Array<ArrayBuffer> | undefined;
  let contentType = "application/json";
  if (request.method === "POST" || request.method === "DELETE") {
    try {
      assertMutation(
        request,
        request.headers.get("x-csrf-token") ?? "",
        locals.binding,
        locals.userId,
        locals.settings,
      );
      const upload = "multipart" in route ? route.multipart : undefined;
      if (upload) {
        // An upload is passed through as bytes with its own boundary; the API validates it.
        const given = request.headers.get("content-type") ?? "";
        if (!/^multipart\/form-data; boundary=[^\s;]+$/.test(given))
          return response("BODY_INVALID", 400);
        contentType = given;
        body = await boundedBytes(request, upload.maxBytes);
      } else {
        if (
          request.method === "POST" &&
          request.headers.get("content-type")?.split(";", 1)[0] !==
            "application/json"
        )
          return response("BODY_INVALID", 400);
        const raw =
          request.method === "DELETE"
            ? {}
            : JSON.parse(await boundedBody(request, 262144));
        if (
          request.method === "DELETE" &&
          (await boundedBody(request, 262144)).length
        )
          return response("BODY_INVALID", 400);
        if (request.method === "DELETE") {
          body = undefined;
        } else {
          if (!("body" in route) || !route.body)
            return response("BODY_INVALID", 400);
          const parsed = route.body.safeParse(raw);
          if (!parsed.success) return response("BODY_INVALID", 400);
          if (route.body === decision) {
            const typed: DecisionBody = parsed.data as DecisionBody;
            body = JSON.stringify(typed);
          } else body = JSON.stringify(parsed.data);
        }
      }
    } catch (error) {
      return response(
        error instanceof Error && error.message === "BODY_TOO_LARGE"
          ? "BODY_TOO_LARGE"
          : "REQUEST_DENIED",
        error instanceof Error && error.message === "BODY_TOO_LARGE"
          ? 413
          : 403,
      );
    }
  }
  const upstream = route.upstream || "/api/v1/" + path.replace(/\/$/, "");
  try {
    const result = await fetcher(
      locals.settings.apiOrigin +
        upstream +
        (query.size ? "?" + query.toString() : ""),
      {
        method: request.method,
        body,
        redirect: "manual",
        signal: AbortSignal.timeout(request.method === "GET" ? 10000 : 30000),
        headers: {
          Authorization: `Bearer ${locals.token}`,
          "Content-Type": contentType,
          "X-Correlation-ID": locals.correlationId,
        },
      },
    );
    if (result.status >= 300 && result.status < 400)
      return response("UPSTREAM_REDIRECT_DENIED", 502);
    if (!result.headers.get("content-type")?.includes("application/json"))
      return response("UPSTREAM_INVALID", 502);
    // Allow JSON application data, never cookies, redirect locations or arbitrary upstream headers.
    const payload = await boundedBody(
      new Request("https://response.invalid", {
        method: "POST",
        body: result.body,
        duplex: "half",
      } as RequestInit),
      2097152,
    );
    const parsed: unknown = JSON.parse(payload);
    if (containsSecret(parsed)) return response("UPSTREAM_SECRET_DENIED", 502);
    return new Response(payload, {
      status: result.status,
      headers: {
        ...privateHeaders,
        "Content-Type": "application/json",
        "X-Correlation-ID": locals.correlationId,
      },
    });
  } catch {
    return response(
      request.method !== "GET"
        ? "MUTATION_OUTCOME_UNCERTAIN"
        : "UPSTREAM_UNAVAILABLE",
      504,
    );
  }
}
function containsSecret(value: unknown): boolean {
  if (!value || typeof value !== "object") return false;
  return Object.entries(value).some(
    ([key, child]) =>
      /^(access_token|refresh_token|password|totp|secret|qr_code|cookie|authorization)$/i.test(
        key,
      ) || containsSecret(child),
  );
}
export async function read<T>(locals: App.Locals, path: string): Promise<T> {
  const result = await forward(
    new Request(locals.settings.origin + "/api/" + path),
    path.split("?", 1)[0],
    locals,
  );
  if (!result.ok) throw new APIError(result.status, "SOURCE_UNAVAILABLE");
  return result.json() as Promise<T>;
}
