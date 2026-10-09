import { failureCode, runFailureText } from "./automation-view";
function show(banner: HTMLElement, code: string) {
  const text = banner.querySelector<HTMLElement>("[data-run-error-text]");
  if (text) text.textContent = runFailureText(code);
  banner.hidden = false;
  banner.focus();
}
function initialize() {
  document
    .querySelectorAll<HTMLButtonElement>("[data-automation-run]")
    .forEach((button) => {
      button.removeAttribute("inert");
      // One key per opened dialog: a retry after an unclear answer starts nothing twice.
      const key = crypto.randomUUID();
      const banner = document.querySelector<HTMLElement>("[data-run-error]");
      const status = document.querySelector<HTMLElement>("[data-run-status]");
      button.addEventListener("click", async () => {
        if (button.disabled) return;
        button.disabled = true;
        if (banner) banner.hidden = true;
        if (status) status.textContent = "Starting the run…";
        try {
          const response = await fetch(button.dataset.automationRun!, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "Idempotency-Key": key,
              "X-CSRF-Token":
                document.querySelector<HTMLMetaElement>(
                  'meta[name="csrf-token"]',
                )?.content ?? "",
            },
            body: "{}",
          });
          if (!response.ok) {
            const raw: unknown = await response.json().catch(() => null);
            if (status) status.textContent = "";
            if (banner) show(banner, failureCode(raw, response.status));
            // A refusal that says why is final; anything else may be tried again.
            button.disabled = response.status < 500 ? true : false;
            return;
          }
          if (status) status.textContent = "Run started. Updating…";
          window.location.reload();
        } catch {
          if (status) status.textContent = "";
          if (banner) show(banner, "UNKNOWN");
          button.disabled = false;
        }
      });
    });
}
initialize();
