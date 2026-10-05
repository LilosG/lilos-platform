import { z } from "zod";
const envelope = z
  .object({
    data: z.unknown().optional(),
    error: z.object({ code: z.string() }).loose().optional(),
    code: z.string().optional(),
  })
  .loose();
/** A failed call: the typed code the server answered with, never shown to a person as is. */
export class ApiFailure extends Error {
  constructor(public code: string) {
    super(code);
  }
}
const csrf = () =>
  document.querySelector<HTMLMetaElement>('meta[name="csrf-token"]')?.content ??
  "";
/** A call through the console's own server, which holds the session and the allow-list. */
export async function action(
  url: string,
  body: unknown,
  method = "POST",
): Promise<unknown> {
  const response = await fetch(url, {
    method,
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf() },
    ...(method === "GET" || method === "DELETE"
      ? {}
      : { body: JSON.stringify(body) }),
  });
  const parsed = envelope.parse(await response.json());
  if (!response.ok || parsed.error || parsed.code)
    throw new ApiFailure(
      parsed.code ?? parsed.error?.code ?? `HTTP_${response.status}`,
    );
  return parsed.data;
}
const known: Record<string, string> = {
  MFA_REQUIRED: "Verify your authenticator, then try again.",
  AAL2_REQUIRED: "Verify your authenticator, then try again.",
  AUTH_REQUIRED: "Your session ended. Sign in again to continue.",
  MUTATION_OUTCOME_UNCERTAIN:
    "We could not confirm what happened. Refresh to see the current state.",
  GBP_LOCATION_NOT_WRITE_ENABLED:
    "Publishing is turned off for this profile. Turn it on in Integrations first.",
  GBP_CAPABILITY_SNAPSHOT_NOT_FOUND:
    "Google has not confirmed what this profile allows yet. Try again after the next sync.",
  GBP_CAPABILITY_UNAVAILABLE:
    "Google does not allow this change for the profile.",
  GBP_POST_NOT_PUBLISH_ELIGIBLE: "Only an approved post can be published.",
  GBP_POST_PUBLICATION_EXISTS: "This post has already been published.",
  GBP_MEDIA_NOT_PUBLISH_ELIGIBLE: "Only an approved photo can be published.",
  GBP_INVALID_HOURS:
    "Those hours are not valid. Check the opening and closing times.",
  GBP_CHANGE_SET_NOT_DECIDABLE: "That change was already decided.",
  BODY_INVALID: "Check the details and try again.",
};
/** A sentence a person can act on for a failed call. */
export function failureText(error: unknown): string {
  const code = error instanceof ApiFailure ? error.code : "";
  return (
    known[code] ??
    "That did not go through. Refresh to see the current state, then try again."
  );
}
