import { reviewFailure } from "./review-actions";
async function send(url: string, body: unknown) {
  const node = document.querySelector<HTMLElement>("[data-lead-status]");
  if (node)
    node.textContent =
      "Request in progress. Inspect recorded state after completion.";
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
      if (node)
        node.textContent = `Action unavailable (${reviewFailure(await response.json(), response.status)}). Refresh to inspect canonical state before trying again.`;
      return;
    }
    window.location.reload();
  } catch {
    if (node)
      node.textContent =
        "Action unavailable or outcome uncertain. Refresh to inspect canonical state before trying again.";
  }
}
function initialize() {
  document
    .querySelectorAll<HTMLFormElement>("[data-lead-form]")
    .forEach((form) => {
      form.removeAttribute("inert");
      form.addEventListener("submit", (event) => {
        event.preventDefault();
        const data = Object.fromEntries(new FormData(form));
        const body =
          form.dataset.leadForm === "convert"
            ? { converted_value_cents: null }
            : {
                ...data,
                ...(form.dataset.leadForm === "communication"
                  ? { idempotency_key: crypto.randomUUID() }
                  : {}),
              };
        form
          .querySelectorAll<HTMLButtonElement>("button")
          .forEach((b) => (b.disabled = true));
        void send(form.dataset.action!, body);
      });
    });
  document
    .querySelectorAll<HTMLButtonElement>("[data-lead-action]")
    .forEach((button) => {
      button.removeAttribute("inert");
      button.addEventListener("click", () => {
        button.disabled = true;
        void send(button.dataset.leadAction!, {});
      });
    });
}
if (typeof document !== "undefined") {
  if (document.readyState === "loading")
    document.addEventListener("DOMContentLoaded", initialize, { once: true });
  else initialize();
}
