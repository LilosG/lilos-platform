import type { ApiOutcome } from "../api-client";

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
    case "error":
      return outcome.message;
    case "ok":
      return "";
  }
}
