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
};
/** What a person reads when an action fails; the code itself is never shown. */
export const failureMessage = (code: string): string =>
  failureText[code] ??
  "That did not go through. Refresh to see the current state before trying again.";
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
        "X-CSRF-Token":
          document.querySelector<HTMLMetaElement>('meta[name="csrf-token"]')
            ?.content ?? "",
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
        const facts = data.getAll("fact");
        if (!facts.length) {
          const node = document.querySelector<HTMLElement>(
            "[data-review-status]",
          );
          if (node)
            node.textContent =
              "Choose at least one business fact the response may use.";
          return;
        }
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
          approved_fact_revision_ids: facts,
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
