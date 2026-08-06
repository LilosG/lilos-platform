import { getAccessToken, refreshAccessToken } from "./session";
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
 * Every request is bounded: a stalled connection (accepted but never
 * responded to — no network error is ever raised for this by `fetch`) must
 * still resolve to a truthful outcome rather than leaving a caller's `await`
 * pending indefinitely, which previously left pages stuck on "Loading…"
 * forever with no way to recover short of a full page reload.
 */
const REQUEST_TIMEOUT_MS = 15_000;

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
 *
 * A 401 is retried exactly once against a forcibly-refreshed token before
 * being reported as `unauthenticated`: a locally-held token can be stale
 * relative to the server (e.g. immediately after an MFA step-up, or after
 * another tab/request rotated the refresh token) even though the caller is
 * genuinely still signed in, and the previous behavior reported that
 * transient staleness as a real sign-out.
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

  const first = await attemptRequest<T>(
    config.apiBaseUrl,
    path,
    options,
    token,
  );
  if (first.kind !== "unauthenticated") {
    return first;
  }

  const refreshedToken = await refreshAccessToken();
  if (!refreshedToken || refreshedToken === token) {
    return first;
  }
  return attemptRequest<T>(config.apiBaseUrl, path, options, refreshedToken);
}

async function attemptRequest<T>(
  apiBaseUrl: string,
  path: string,
  options: ApiRequestOptions,
  token: string,
): Promise<ApiOutcome<T>> {
  const method = options.method ?? "GET";
  let response: Response;
  const timeoutController = new AbortController();
  const timeoutId = setTimeout(
    () => timeoutController.abort(),
    REQUEST_TIMEOUT_MS,
  );
  try {
    response = await fetch(`${apiBaseUrl}${path}`, {
      method,
      headers: {
        Authorization: `Bearer ${token}`,
        ...(options.body !== undefined
          ? { "Content-Type": "application/json" }
          : {}),
      },
      body:
        options.body !== undefined ? JSON.stringify(options.body) : undefined,
      signal: timeoutController.signal,
    });
  } catch {
    // Covers both a genuine network failure and a timed-out (aborted)
    // request — either way the caller could not complete the request and
    // must render that truthfully rather than hang.
    return { kind: "disconnected" };
  } finally {
    clearTimeout(timeoutId);
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
