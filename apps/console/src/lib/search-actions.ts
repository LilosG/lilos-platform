import { action } from "./api-client";
const status = () =>
  document.querySelector<HTMLElement>("[data-search-status]");
function message(text: string) {
  const node = status();
  if (node) node.textContent = text;
}
/** Local Search's own actions (a website check). Integrations has its own script. */
function initialize() {
  document
    .querySelectorAll<HTMLButtonElement>("button[data-action]")
    .forEach((button) => {
      button.addEventListener("click", async () => {
        button.disabled = true;
        message("Starting the check…");
        try {
          const body = button.hasAttribute("data-key")
            ? { idempotency_key: crypto.randomUUID() }
            : JSON.parse(button.dataset.body ?? "{}");
          await action(button.dataset.action!, body, button.dataset.method);
          window.location.reload();
        } catch {
          button.disabled = false;
          message(
            "That did not start. Refresh to see the current state, then try again.",
          );
        }
      });
      button.removeAttribute("inert");
    });
}
if (document.readyState === "loading")
  document.addEventListener("DOMContentLoaded", initialize, { once: true });
else initialize();
