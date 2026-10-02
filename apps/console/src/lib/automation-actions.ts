import { reviewFailure } from "./review-actions";
async function send(url: string, method: string, body: unknown) {
  const status = document.querySelector<HTMLElement>(
    "[data-automation-status]",
  );
  if (status)
    status.textContent =
      "Request in progress. Completion awaits canonical recorded state.";
  try {
    const response = await fetch(url, {
      method,
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token":
          document.querySelector<HTMLMetaElement>('meta[name="csrf-token"]')
            ?.content ?? "",
      },
      body: JSON.stringify(body),
    });
    if (!response.ok) {
      if (status)
        status.textContent = `Action unavailable (${reviewFailure(await response.json(), response.status)}). Refresh to inspect recorded state before trying again.`;
      return;
    }
    window.location.reload();
  } catch {
    if (status)
      status.textContent =
        "Outcome uncertain. Refresh to inspect recorded state before trying again.";
  }
}
function initialize() {
  document
    .querySelectorAll<HTMLButtonElement>("[data-automation-action]")
    .forEach((b) => {
      b.removeAttribute("inert");
      b.addEventListener("click", () => {
        b.disabled = true;
        const command = b.dataset.command!;
        const body =
          command === "run"
            ? {
                input_document: {},
                execute: true,
                idempotency_key: crypto.randomUUID(),
                location_id: b.dataset.location || null,
              }
            : ["paused", "active"].includes(command)
              ? { status: command }
              : ["once", "deny"].includes(command)
                ? { choice: command }
                : {};
        void send(
          b.dataset.automationAction!,
          b.dataset.method ?? "POST",
          body,
        );
      });
    });
  document
    .querySelectorAll<HTMLFormElement>("[data-automation-form]")
    .forEach((form) => {
      form.removeAttribute("inert");
      form.addEventListener("submit", (event) => {
        event.preventDefault();
        form
          .querySelectorAll<HTMLButtonElement>("button")
          .forEach((b) => (b.disabled = true));
        void send(form.dataset.action!, "POST", {
          ...Object.fromEntries(new FormData(form)),
          ...(form.dataset.automationForm === "agent"
            ? { idempotency_key: crypto.randomUUID() }
            : form.dataset.automationForm === "schedule"
              ? { location_id: new FormData(form).get("location_id") || null }
              : {}),
        });
      });
    });
}
if (typeof document !== "undefined") {
  if (document.readyState === "loading")
    document.addEventListener("DOMContentLoaded", initialize, { once: true });
  else initialize();
}
