import { getAccessToken } from "./session";
import { readPublicConfig } from "./config";

export type ApiErrorDetail = { field?: string; code?: string; message: string };

export type ApiOutcome<T> =
  | { kind: "ok"; data: T }
  | { kind: "not-configured" }
  | { kind: "unauthenticated" }
  | { kind: "forbidden" }
  | { kind: "not-found" }
  | { kind: "disconnected" }
  | {
      kind: "error";
      status: number;
      code: string;
      message: string;
      details: ApiErrorDetail[];
    };

type ErrorEnvelope = {
  error?: { code?: string; message?: string; details?: ApiErrorDetail[] };
};

export type ApiRequestOptions = {
  method?: "GET" | "POST" | "PUT" | "DELETE";
  body?: unknown;
};

/**
 * Authenticated GET against the LILOs API. Never fabricates a result: a missing
 * configuration, missing session, network failure, or non-2xx response each map
 * to a distinct outcome the caller must render truthfully.
 */
export function apiGet<T>(path: string): Promise<ApiOutcome<T>> {
  return apiRequest<T>(path);
}

/**
 * Authenticated request (GET/POST/PUT/DELETE) against the LILOs API, sharing
 * the exact same truthful-outcome classification as `apiGet`. State-changing
 * callers pass `method` and an optional JSON-serializable `body`.
 */
export async function apiRequest<T>(
  path: string,
  options: ApiRequestOptions = {},
): Promise<ApiOutcome<T>> {
  const config = readPublicConfig();
  if (!config) {
    return { kind: "not-configured" };
  }
  const token = await getAccessToken();
  if (!token) {
    return { kind: "unauthenticated" };
  }
  const method = options.method ?? "GET";
  let response: Response;
  try {
    response = await fetch(`${config.apiBaseUrl}${path}`, {
      method,
      headers: {
        Authorization: `Bearer ${token}`,
        ...(options.body !== undefined
          ? { "Content-Type": "application/json" }
          : {}),
      },
      body:
        options.body !== undefined ? JSON.stringify(options.body) : undefined,
    });
  } catch {
    return { kind: "disconnected" };
  }
  if (response.status === 401) {
    return { kind: "unauthenticated" };
  }
  if (response.status === 403) {
    return { kind: "forbidden" };
  }
  if (response.status === 404) {
    return { kind: "not-found" };
  }
  if (!response.ok) {
    const envelope = await safeJson<ErrorEnvelope>(response);
    return {
      kind: "error",
      status: response.status,
      code: envelope?.error?.code ?? "UNKNOWN_ERROR",
      message: envelope?.error?.message ?? "The request failed.",
      details: envelope?.error?.details ?? [],
    };
  }
  const body = await safeJson<{ data: T }>(response);
  if (!body) {
    return {
      kind: "error",
      status: response.status,
      code: "INVALID_RESPONSE",
      message: "The response could not be read.",
      details: [],
    };
  }
  return { kind: "ok", data: body.data };
}

async function safeJson<T>(response: Response): Promise<T | null> {
  try {
    return (await response.json()) as T;
  } catch {
    return null;
  }
}
