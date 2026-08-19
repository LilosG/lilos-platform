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
    case "forbidden":
      return `${prefix}You do not have permission to view this.`;
    case "not-found":
      return `${prefix}The requested resource could not be found.`;
    case "disconnected":
      return `${prefix}Could not reach the platform API.`;
    case "unauthenticated":
      return `${prefix}Your session has expired. Sign in again.`;
    case "not-configured":
      return `${prefix}This deployment is not configured.`;
    case "error": {
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
