import { z } from "zod";
import { photoProblemText } from "./photo-check";
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
/** A call through the console's own server, which holds the session and the allow-list.
 * Returns the whole answer: command-center routes answer with the model itself, not a `data` envelope. */
export async function call(
  url: string,
  body: unknown,
  method = "POST",
  headers: Record<string, string> = {},
): Promise<unknown> {
  const response = await fetch(url, {
    method,
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": csrf(),
      ...headers,
    },
    ...(method === "GET" || method === "DELETE"
      ? {}
      : { body: JSON.stringify(body) }),
  });
  const parsed = envelope.parse(await response.json());
  if (!response.ok || parsed.error || parsed.code)
    throw new ApiFailure(
      parsed.code ?? parsed.error?.code ?? `HTTP_${response.status}`,
    );
  return parsed;
}
/** A call whose answer is wrapped as `{ data }`. */
export async function action(
  url: string,
  body: unknown,
  method = "POST",
  headers: Record<string, string> = {},
): Promise<unknown> {
  return (
    envelope.parse(await call(url, body, method, headers)) as {
      data?: unknown;
    }
  ).data;
}
/** An upload with its progress, which `fetch` cannot report. Sent as multipart through the
 * console's own server, which holds the session. */
export function upload(
  url: string,
  form: FormData,
  onProgress: (fraction: number) => void,
): Promise<unknown> {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("POST", url);
    request.setRequestHeader("X-CSRF-Token", csrf());
    request.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(event.loaded / event.total);
    };
    request.onerror = () => reject(new ApiFailure("UPLOAD_FAILED"));
    request.onload = () => {
      try {
        const parsed = envelope.parse(JSON.parse(request.responseText));
        if (request.status >= 400 || parsed.error || parsed.code)
          reject(
            new ApiFailure(
              parsed.code ?? parsed.error?.code ?? `HTTP_${request.status}`,
            ),
          );
        else resolve(parsed.data);
      } catch {
        reject(new ApiFailure(`HTTP_${request.status}`));
      }
    };
    request.send(form);
  });
}
const known: Record<string, string> = {
  ...photoProblemText,
  STORAGE_NOT_CONFIGURED:
    "Photo uploads are not set up yet. Ask an administrator to finish setup.",
  UPLOAD_FAILED:
    "The upload was interrupted. Check your connection and try again.",
  BODY_TOO_LARGE: photoProblemText.MEDIA_TOO_LARGE,
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
