import { getAccessToken } from "./session";
import { readPublicConfig } from "./config";

export type ApiOutcome<T> =
  | { kind: "ok"; data: T }
  | { kind: "not-configured" }
  | { kind: "unauthenticated" }
  | { kind: "forbidden" }
  | { kind: "not-found" }
  | { kind: "disconnected" }
  | { kind: "error"; status: number; code: string; message: string };

type ErrorEnvelope = { error?: { code?: string; message?: string } };

/**
 * Authenticated GET against the LILOs API. Never fabricates a result: a missing
 * configuration, missing session, network failure, or non-2xx response each map
 * to a distinct outcome the caller must render truthfully.
 */
export async function apiGet<T>(path: string): Promise<ApiOutcome<T>> {
  const config = readPublicConfig();
  if (!config) {
    return { kind: "not-configured" };
  }
  const token = await getAccessToken();
  if (!token) {
    return { kind: "unauthenticated" };
  }
  let response: Response;
  try {
    response = await fetch(`${config.apiBaseUrl}${path}`, {
      headers: { Authorization: `Bearer ${token}` },
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
    };
  }
  const body = await safeJson<{ data: T }>(response);
  if (!body) {
    return {
      kind: "error",
      status: response.status,
      code: "INVALID_RESPONSE",
      message: "The response could not be read.",
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
