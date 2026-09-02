import type { ApiOutcome } from "../api-client";

/**
 * Human-readable failure message derived from a typed API outcome.
 *
 * When the backend returns field-level validation details (e.g.
 * `{ field: "intent", message: "Content goal must be 500 characters
 * or fewer." }`) those details are surfaced in priority over the
 * generic envelope message.
 */
export function describeFailure(
  outcome: ApiOutcome<unknown>,
  context?: string,
): string {
  const prefix = context ? `${context}: ` : "";
  switch (outcome.kind) {
    case "forbidden": {
      // The backend names the cause and what to do about it whenever the
      // caller is a confirmed member; only the deliberately non-disclosing
      // generic denial falls back to the canned sentence, which is more
      // specific than "Authorization is required for this action."
      const named =
        outcome.code && outcome.code !== "AUTHORIZATION_DENIED"
          ? outcome.message?.trim()
          : undefined;
      return named
        ? `${prefix}${named}`
        : `${prefix}You do not have permission to view this.`;
    }
    case "not-found":
      return `${prefix}The requested resource could not be found.`;
    case "disconnected":
      return `${prefix}Could not reach the platform API.`;
    case "unauthenticated":
      return `${prefix}Your session has expired. Sign in again.`;
    case "not-configured":
      return `${prefix}This deployment is not configured.`;
    case "error": {
      if (outcome.code === "REQUEST_TIMEOUT") {
        return `${prefix}${outcome.message}`;
      }
      // Field-level validation details take priority.
      const details = outcome.details;
      if (details && details.length > 0) {
        const fieldMessages = details
          .filter((d) => d.message?.trim())
          .map((d) => (d.field ? `${d.message}` : d.message))
          .join(" ");
        if (fieldMessages) return fieldMessages;
      }
      return outcome.message || `${prefix}The request failed.`;
    }
    case "ok":
      return "";
  }
}
