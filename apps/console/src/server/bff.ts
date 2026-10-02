import { z } from "zod";
import { leadRoutes } from "./lead-routes";
import { websiteRoutes } from "./website-routes";
import { reviewRoutes } from "./review-routes";
import { searchRoutes } from "./search-routes";
import { assertMutation, boundedBody, privateHeaders } from "./security";
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
    pattern: new RegExp(
      `^organizations/${uuid}/command-center/(opportunities|attention)/$`,
    ),
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
] as const;
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
      (key === "website_id" || key === "location_id" || key === "target_id"
        ? !z.uuid().safeParse(value).success
        : !/^\d+$/.test(value)) ||
      query.getAll(key).length !== 1 ||
      (key !== "website_id" &&
        key !== "location_id" &&
        key !== "target_id" &&
        Number(value) > (key === "limit" ? 100 : 100000)) ||
      (key === "days" && ![7, 28, 90].includes(Number(value))) ||
      (key === "limit" && Number(value) < 1)
    )
      return response("QUERY_INVALID", 400);
  }
  let body: string | undefined;
  if (request.method === "POST" || request.method === "DELETE") {
    try {
      assertMutation(
        request,
        request.headers.get("x-csrf-token") ?? "",
        locals.binding,
        locals.userId,
        locals.settings,
      );
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
          "Content-Type": "application/json",
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
