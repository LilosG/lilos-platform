import { ApiFailure, action } from "./api-client";
const status = () =>
  document.querySelector<HTMLElement>("[data-website-status]");
const message = (text: string) => {
  const node = status();
  if (node) node.textContent = text;
};
/** What a person is told when a check cannot start; the server's code never reaches them. */
const failureText: Record<string, string> = {
  HTTP_403: "You do not have access to start website checks.",
  AUTH_AAL2_REQUIRED: "Confirm your sign-in with your authenticator first.",
};
export const failureMessage = (error: unknown): string =>
  (error instanceof ApiFailure && failureText[error.code]) ||
  "The website check could not be started. Try again in a moment.";
document
  .querySelectorAll<HTMLButtonElement>("button[data-website-check]")
  .forEach((button) => {
    button.removeAttribute("inert");
    button.addEventListener("click", async () => {
      const all = document.querySelectorAll<HTMLButtonElement>(
        "button[data-website-check]",
      );
      all.forEach((other) => (other.disabled = true));
      message("Starting the website check…");
      try {
        await action(button.dataset.websiteCheck!, {
          idempotency_key: crypto.randomUUID(),
        });
        message(
          "Website check started. Refresh in a few minutes to see the results.",
        );
      } catch (error) {
        message(failureMessage(error));
        all.forEach((other) => (other.disabled = false));
      }
    });
  });
