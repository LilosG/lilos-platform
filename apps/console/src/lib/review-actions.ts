import { z } from "zod";
const code = z.string().regex(/^[A-Z][A-Z0-9_]{0,127}$/);
export function reviewFailure(raw: unknown, status: number): string {
  const parsed = z
    .object({
      code: code.optional(),
      error: z.object({ code }).loose().optional(),
    })
    .loose()
    .safeParse(raw);
  return parsed.success
    ? (parsed.data.error?.code ?? parsed.data.code ?? `HTTP_${status}`)
    : `HTTP_${status}`;
}
const failureText: Record<string, string> = {
  AAL2_REQUIRED: "Verify your authenticator, then try again.",
  CSRF_INVALID: "Your session expired. Refresh the page and try again.",
  RECONNECT_REQUIRED:
    "Google needs to be reconnected for this client. Open Integrations to reconnect.",
  INGEST_STILL_RUNNING:
    "Still importing in the background. Refresh in a minute.",
  REVIEW_NO_LONGER_ON_PROVIDER:
    "Google no longer lists this review, so it cannot be replied to. Refresh to see the current state.",
};
/** What a person reads when an action fails; the code itself is never shown. */
export const failureMessage = (code: string): string =>
  failureText[code] ??
  "That did not go through. Refresh to see the current state before trying again.";
export const INGEST_WORKING = "Importing reviews. This can take a minute.";
export const INGEST_POLL_MS = 3000;
export const INGEST_LIMIT_MS = 300000;
const ingestStarted = z.object({ run_id: z.uuid() }).loose();
const ingestStatus = z.object({
  result: z.enum(["SUCCEEDED", "RECONNECT_REQUIRED", "FAILED"]).nullable(),
});
/** How an import ended; the code is turned into words by `failureMessage`. */
export type IngestOutcome =
  "SUCCEEDED" | "RECONNECT_REQUIRED" | "FAILED" | "INGEST_STILL_RUNNING";
const pause = (ms: number) => new Promise((done) => setTimeout(done, ms));
/**
 * Queue a review import, then poll its run until it finishes. A failed poll is never an
 * answer while the import may still be going, so only a finished run or the time limit
 * ends it.
 */
export async function importReviews(
  url: string,
  headers: Record<string, string>,
  options: {
    fetcher?: typeof fetch;
    wait?: (ms: number) => Promise<unknown>;
    pollMs?: number;
    limitMs?: number;
    key?: string;
  } = {},
): Promise<IngestOutcome | { failure: string }> {
  const fetcher = options.fetcher ?? fetch;
  const wait = options.wait ?? pause;
  const pollMs = options.pollMs ?? INGEST_POLL_MS;
  const polls = Math.ceil((options.limitMs ?? INGEST_LIMIT_MS) / pollMs);
  const started = await fetcher(url, {
    method: "POST",
    headers: {
      ...headers,
      "Content-Type": "application/json",
      "Idempotency-Key": options.key ?? crypto.randomUUID(),
    },
    body: "{}",
  });
  if (!started.ok)
    return { failure: reviewFailure(await started.json(), started.status) };
  const run = ingestStarted.safeParse(await started.json());
  if (!run.success) return "FAILED";
  for (let poll = 0; poll < polls; poll++) {
    await wait(pollMs);
    try {
      const response = await fetcher(`${url}${run.data.run_id}/`, {
        headers,
      });
      if ([401, 403, 404].includes(response.status)) return "FAILED";
      if (!response.ok) continue;
      const status = ingestStatus.safeParse(await response.json());
      if (status.success && status.data.result) return status.data.result;
    } catch {
      // The import goes on in the background; ask again.
    }
  }
  return "INGEST_STILL_RUNNING";
}
const csrf = () =>
  document.querySelector<HTMLMetaElement>('meta[name="csrf-token"]')?.content ??
  "";
const ingestButtons = () =>
  document.querySelectorAll<HTMLButtonElement>("[data-review-ingest]");
async function ingest(url: string) {
  ingestButtons().forEach((b) => (b.disabled = true));
  const node = document.querySelector<HTMLElement>("[data-review-status]");
  if (node) {
    node.textContent = INGEST_WORKING;
    node.dataset.state = "working";
  }
  let outcome: Awaited<ReturnType<typeof importReviews>>;
  try {
    outcome = await importReviews(url, { "X-CSRF-Token": csrf() });
  } catch {
    outcome = {
      failure: "MUTATION_OUTCOME_UNCERTAIN",
    };
  }
  if (outcome === "SUCCEEDED") {
    window.location.reload();
    return;
  }
  if (node) {
    delete node.dataset.state;
    node.textContent = failureMessage(
      typeof outcome === "string" ? outcome : outcome.failure,
    );
  }
  if (outcome !== "INGEST_STILL_RUNNING")
    ingestButtons().forEach((b) => (b.disabled = false));
}
async function send(url: string, body: unknown) {
  const node = document.querySelector<HTMLElement>("[data-review-status]");
  if (node)
    node.textContent =
      "Working on it. Nothing is confirmed until this finishes.";
  try {
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": csrf(),
      },
      body: JSON.stringify(body),
    });
    if (!response.ok) {
      const raw: unknown = await response.json();
      if (node)
        node.textContent = failureMessage(reviewFailure(raw, response.status));
      return;
    }
    window.location.reload();
  } catch {
    if (node)
      node.textContent =
        "We could not confirm the result. Refresh to see the current state before trying again.";
  }
}
function initialize() {
  document
    .querySelectorAll<HTMLButtonElement>("[data-review-ingest]")
    .forEach((button) => {
      button.removeAttribute("inert");
      button.addEventListener("click", () => {
        void ingest(button.dataset.reviewIngest!);
      });
    });
  document
    .querySelectorAll<HTMLButtonElement>("[data-review-action]")
    .forEach((button) => {
      button.removeAttribute("inert");
      button.addEventListener("click", () => {
        button.disabled = true;
        void send(
          button.dataset.reviewAction!,
          button.dataset.key ? { idempotency_key: button.dataset.key } : {},
        );
      });
    });
  document
    .querySelectorAll<HTMLFormElement>("[data-review-draft]")
    .forEach((form) => {
      form.removeAttribute("inert");
      form.addEventListener("submit", (event) => {
        event.preventDefault();
        const data = new FormData(form);
        const ai =
          (event as SubmitEvent).submitter instanceof HTMLButtonElement &&
          ((event as SubmitEvent).submitter as HTMLButtonElement).value ===
            "ai";
        if (!ai && !String(data.get("response_text") ?? "").trim()) {
          const node = document.querySelector<HTMLElement>(
            "[data-review-status]",
          );
          if (node) node.textContent = "Write a response first.";
          return;
        }
        form
          .querySelectorAll<HTMLButtonElement>("button")
          .forEach((b) => (b.disabled = true));
        void send(form.dataset.action! + (ai ? "ai-draft/" : ""), {
          review_revision_id: form.dataset.revision,
          ...(ai
            ? { idempotency_key: crypto.randomUUID() }
            : {
                response_text: data.get("response_text"),
                generated_by_type: "user",
              }),
        });
      });
    });
}
if (typeof document !== "undefined") {
  if (document.readyState === "loading")
    document.addEventListener("DOMContentLoaded", initialize, { once: true });
  else initialize();
}
